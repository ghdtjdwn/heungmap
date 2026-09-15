"""검증된 로컬 artifact만 사용하는 공용 수요 예측 adapter."""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from app.schemas import (
    AvailablePrediction, Evidence, PredictionComponent, PredictionFactor,
    PredictionIndicators, PredictionRangeMetric, PredictionResult, RegionRef,
    SourceRef, UnavailablePrediction,
)

DEFAULT_DIRECTORY = Path(__file__).resolve().parents[3] / "data" / "processed" / "demand-model-release"
AREA_TO_ADMIN = {"1": "11", "2": "28", "3": "30", "4": "27", "5": "29", "6": "26", "7": "31", "8": "36", "31": "41", "32": "51", "33": "43", "34": "44", "35": "47", "36": "48", "37": "45", "38": "46", "39": "50"}
ADMIN_TO_AREA = {value: key for key, value in AREA_TO_ADMIN.items()}
# 전북특별자치도 신규 법정코드는 기존 TourAPI 전북 지역과 대응한다.
ADMIN_TO_AREA["52"] = "37"
FEATURE_LABELS = {
    "month_sin": "개최 계절", "month_cos": "개최 계절", "duration_days": "행사 기간",
    "calendar_expected_uplift": "과거 지역 요일 패턴", "history_trend_28d": "과거 지역 수요 변화",
    "history_volatility": "과거 수요 변동", "history_weekend_ratio": "주말·평일 지역 수요 차이",
    "log_history_level": "과거 지역 수요 규모", "province_code": "광역 지역",
    **{f"weekday_{i}_fraction": f"{'월화수목금토일'[i]}요일 비중" for i in range(7)},
}


def _directory() -> Path:
    return Path(os.environ.get("HEUNGMAP_DEMAND_MODEL_DIR", str(DEFAULT_DIRECTORY))).resolve()


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@lru_cache(maxsize=2)
def _load(directory: str, file_state: tuple):
    # optional model dependencies are loaded only when a complete artifact exists.
    import lightgbm as lgb
    import numpy as np
    from app.demand.data import FEATURES, load_daily_history

    root = Path(directory)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("모델 manifest는 객체여야 합니다.")
    if manifest.get("schema_version") != "1.0" or manifest.get("features") != FEATURES:
        raise ValueError("지원하지 않는 모델 artifact입니다.")
    if not isinstance(manifest.get("model_version"), str) or not 1 <= len(manifest["model_version"]) <= 100:
        raise ValueError("모델 버전 정보가 잘못됐습니다.")
    for name in ("created_at", "festival_retrieved_at"):
        timestamp = datetime.fromisoformat(manifest[name])
        if timestamp.tzinfo is None:
            raise ValueError("모델 출처 시각에 시간대가 없습니다.")
    for name in ("training_end", "data_end"):
        date.fromisoformat(manifest[name])
    if not isinstance(manifest.get("limitations"), list) or not manifest["limitations"] or any(not isinstance(item, str) for item in manifest["limitations"]):
        raise ValueError("모델 한계 정보가 잘못됐습니다.")
    if not isinstance(manifest.get("regions"), list) or not manifest["regions"]:
        raise ValueError("모델 지역 정보가 없습니다.")
    for item in manifest["regions"]:
        if not re.fullmatch(r"[0-9]{5}", item["code"]) or not isinstance(item["name"], str) or not item["name"]:
            raise ValueError("모델 지역 정보가 잘못됐습니다.")
    scope = manifest["training_scope"]
    if not isinstance(scope["regions"], list) or not scope["regions"] or set(scope["feature_ranges"]) != set(FEATURES):
        raise ValueError("모델 학습 범위 정보가 잘못됐습니다.")
    bounds = np.asarray([scope["feature_ranges"][name] for name in FEATURES], dtype=float)
    if bounds.shape != (len(FEATURES), 2) or not np.isfinite(bounds).all() or (bounds[:, 0] > bounds[:, 1]).any():
        raise ValueError("모델 학습 범위가 잘못됐습니다.")
    parameters = manifest["parameters"]
    if parameters["objective"] != "regression_l1" or not isinstance(parameters["residual"], bool) or not 0 < parameters["model_weight"] <= 1:
        raise ValueError("중앙값 모델의 설정이 잘못됐습니다.")
    expected_files = {"p10.txt", "p50.txt", "p90.txt", "history.csv", "evaluation.json"}
    if set(manifest.get("files", {})) != expected_files:
        raise ValueError("모델 artifact가 완전하지 않습니다.")
    for name in sorted(expected_files):
        if _digest(root / name) != manifest["files"][name]:
            raise ValueError("모델 artifact 무결성 검사에 실패했습니다.")
    report = json.loads((root / "evaluation.json").read_text(encoding="utf-8"))
    if not isinstance(report, dict) or not isinstance(report.get("adoption_checks"), dict):
        raise ValueError("모델 평가 기록 형식이 잘못됐습니다.")
    if manifest.get("model_adopted") is not True or report.get("model_adopted") is not True or not all(report.get("adoption_checks", {}).values()):
        raise ValueError("평가 채택 기준을 통과한 모델이 없습니다.")
    if not report.get("adoption_checks") or report.get("features") != FEATURES:
        raise ValueError("모델 평가 기록이 잘못됐습니다.")
    if manifest["model_version"] != report["model_version"]:
        raise ValueError("모델 버전과 평가 기록이 일치하지 않습니다.")
    if manifest["parameters"] != report["selected_candidate"]["parameters"]:
        raise ValueError("학습·추론 설정이 일치하지 않습니다.")
    if manifest["residual_quantiles"] != report["selected_candidate"]["residual_quantiles"] or scope != report["training_scope"]:
        raise ValueError("학습·추론 범위 보정 또는 학습 범위가 일치하지 않습니다.")
    correction = np.asarray(manifest["residual_quantiles"], dtype=float)
    if correction.shape != (2,) or not np.isfinite(correction).all() or correction[0] > correction[1]:
        raise ValueError("예측 범위 보정값이 잘못됐습니다.")
    try:
        models = [lgb.Booster(model_file=str(root / f"{name}.txt")) for name in ("p10", "p50", "p90")]
    except lgb.basic.LightGBMError as exc:
        raise ValueError("네이티브 모델을 읽을 수 없습니다.") from exc
    if any(model.feature_name() != FEATURES for model in models):
        raise ValueError("저장 모델의 입력 순서가 일치하지 않습니다.")
    daily = load_daily_history(root / "history.csv")
    histories = {str(code): group for code, group in daily.groupby("region_code")}
    return manifest, models, histories


def _artifact():
    directory = _directory()
    # 이미 로드한 모델도 파일 교체·손상 시 다시 검증한다.
    files = ("manifest.json", "p10.txt", "p50.txt", "p90.txt", "history.csv", "evaluation.json")
    state = tuple((name, (directory / name).stat().st_mtime_ns, (directory / name).stat().st_size) for name in files)
    return _load(str(directory), state)


def prediction_regions() -> list[RegionRef]:
    try:
        manifest, _, histories = _artifact()
        regions = []
        for item in manifest["regions"]:
            code = item["code"]
            area = ADMIN_TO_AREA.get(code[:2])
            if area and code in histories:
                regions.append(RegionRef(area_code=area, legal_dong_code=code, display_name=item["name"]))
        return sorted(regions, key=lambda region: (region.area_code, region.display_name))
    except (OSError, ValueError, KeyError, TypeError, ImportError):
        return []


def _unavailable(event_id, now, reason, message):
    return UnavailablePrediction(
        status="unavailable", event_id=event_id, reason_code=reason, message=message,
        as_of=now, sources=[], limitations=["지역 방문수요는 특정 행사 관람객 수가 아닙니다."],
        retryable=False, is_mock=False,
    )


def predict_demand(*, event_id: str, start_date: date, end_date: date, region: RegionRef,
                   event_type: str, as_of: datetime | None = None) -> PredictionResult:
    now = as_of or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("예측 기준시각에는 시간대가 필요합니다.")
    now = now.astimezone(ZoneInfo("Asia/Seoul"))
    if event_type not in {"festival", "local_event"}:
        return _unavailable(event_id, now, "unsupported_event_type", "축제·지역 행사에 대해서만 지역 방문수요를 예측합니다.")
    code = region.legal_dong_code if region else None
    if not code or not re.fullmatch(r"\d{5}", code) or code.endswith("000"):
        return _unavailable(event_id, now, "missing_required_input", "지역 방문수요를 계산하려면 지원 시군구를 선택해 주세요.")
    if ADMIN_TO_AREA.get(code[:2]) != region.area_code:
        return _unavailable(event_id, now, "missing_required_input", "광역 지역과 시군구가 일치하지 않습니다.")
    days_until = (start_date - now.date()).days
    if not 0 <= days_until <= 30 or not 1 <= (end_date - start_date).days + 1 <= 30:
        return _unavailable(event_id, now, "insufficient_data", "현재 모델은 30일 이내 시작하며 1~30일간 열리는 행사만 지원합니다.")
    try:
        manifest, models, histories = _artifact()
    except (OSError, ValueError, KeyError, TypeError, ImportError):
        return _unavailable(event_id, now, "model_unavailable", "검증을 통과한 수요 모델을 불러올 수 없습니다. 입력과 규칙 추천은 유지됩니다.")
    try:
        import lightgbm as lgb
        import numpy as np
        import pandas as pd
        from app.demand.data import FEATURES, InsufficientHistoryError, make_features

        if code not in {item["code"] for item in manifest["regions"]}:
            return _unavailable(event_id, now, "insufficient_data", "이 시군구는 현재 모델의 검증 범위에 포함되지 않습니다.")
        created = datetime.fromisoformat(manifest["created_at"])
        if created > now or now.date() - date.fromisoformat(manifest["data_end"]) > timedelta(days=60):
            return _unavailable(event_id, now, "insufficient_data", "예측 기준시각에 맞는 최신 모델·방문자 이력이 필요합니다.")
        history = histories[code]
        # 실제 온라인 요청에서는 수집되지 않았던 자료도 참조하지 않는다.
        history = history[pd.to_datetime(history.retrieved_at, utc=True) <= now.astimezone(timezone.utc)]
        inputs = make_features(start_date, end_date, code, history)
        bounds = manifest["training_scope"]["feature_ranges"]
        outside = code not in manifest["training_scope"]["regions"] or any(
            value < bounds[name][0] - 1e-9 or value > bounds[name][1] + 1e-9 for name, value in inputs.items()
        )
        frame = pd.DataFrame([inputs], columns=FEATURES)
        residual_weight = manifest["parameters"].get("model_weight", 1.0)
        baseline = inputs["calendar_expected_uplift"] * (1 if manifest["parameters"]["residual"] else 1 - residual_weight)
        raw = [float(model.predict(frame, num_threads=1)[0]) for model in models]
        center = max(-1.0, baseline + residual_weight * raw[1])
        lower = max(-1.0, min(baseline + residual_weight * raw[0], center + min(0, manifest["residual_quantiles"][0])))
        upper = max(center, baseline + residual_weight * raw[2], center + max(0, manifest["residual_quantiles"][1]))
        if not np.isfinite([lower, center, upper]).all():
            raise ValueError("유한하지 않은 모델 예측값입니다.")
        contributions = np.asarray(models[1].predict(frame, pred_contrib=True, num_threads=1))[0] * residual_weight
        if not np.isclose(contributions.sum() + baseline, raw[1] * residual_weight + baseline):
            raise ValueError("모델 설명의 합산 검증에 실패했습니다.")
    except InsufficientHistoryError:
        return _unavailable(event_id, now, "insufficient_data", "해당 시군구·일정의 연속된 과거 방문자 이력이 부족합니다.")
    except (OSError, ValueError, KeyError, TypeError, lgb.basic.LightGBMError):
        return _unavailable(event_id, now, "model_unavailable", "모델 입력 또는 계산 검증에 실패했습니다. 입력과 규칙 추천은 유지됩니다.")
    cutoff = start_date - timedelta(days=60)
    sources = [
        SourceRef(source_id="src_demand_model", source_type="heungmap_model", provider_name="흥할지도",
                  dataset_name=manifest["model_version"], retrieved_at=created,
                  limitation="후향 시간·지역 평가를 통과한 모델이며 실시간 관람객 관측이 아닙니다."),
        SourceRef(source_id="src_demand_visitors", source_type="kto_datalab", provider_name="한국관광공사",
                  dataset_name="지역별 방문자수", source_url="https://www.data.go.kr/data/15101972/openapi.do",
                  retrieved_at=pd.to_datetime(history.retrieved_at, utc=True).max().to_pydatetime(),
                  data_as_of=datetime.combine(cutoff, datetime.min.time(), tzinfo=now.tzinfo),
                  limitation="이동통신 기반 지역 방문자-일 집계이며 현지인·외지인·외국인을 합산했습니다."),
        SourceRef(source_id="src_demand_festivals", source_type="tourapi", provider_name="한국관광공사",
                  dataset_name="국문 관광정보 searchFestival2 학습 행사 일정",
                  source_url="https://www.data.go.kr/data/15101578/openapi.do", retrieved_at=datetime.fromisoformat(manifest["festival_retrieved_at"]),
                  limitation="사후 수집한 행사 일정으로 평가했으며 행사 자체 효과를 분리하지 못합니다."),
    ]
    evidence = [Evidence(
        evidence_id="ev_demand_history", value_type="derived_value", label="모델이 사용한 과거 지역 수요",
        display_value=f"{(cutoff - timedelta(days=83)).isoformat()}~{cutoff.isoformat()} 지역 일별 방문자 이력",
        source_refs=["src_demand_visitors"], as_of=sources[1].data_as_of,
        limitation="행사 시작60일 전까지의84일 이력만 입력으로 사용합니다.",
    )]
    evidence.extend([
        Evidence(evidence_id="ev_demand_model_base", value_type="model_prediction", label="학습 모델 기준 기여",
                 display_value=f"{contributions[-1] * 100:+.3f}%p", numeric_value=float(contributions[-1] * 100),
                 unit="percentage_points", source_refs=["src_demand_model"]),
        Evidence(evidence_id="ev_demand_weekday_base", value_type="derived_value", label="지역 요일 기준 기여",
                 display_value=f"{baseline * 100:+.3f}%p", numeric_value=baseline * 100,
                 unit="percentage_points", source_refs=["src_demand_visitors"]),
    ])
    factors = []
    selected_indices = sorted(range(len(FEATURES)), key=lambda i: abs(contributions[i]), reverse=True)[:5]
    for index in selected_indices:
        effect = float(contributions[index]) * 100
        factors.append(PredictionFactor(
            factor_id=f"shap_{FEATURES[index]}", label=FEATURE_LABELS[FEATURES[index]],
            direction="up" if effect > 0 else "down" if effect < 0 else "neutral", importance=abs(effect),
            explanation=f"학습 모델 부분에서 기준값 대비 {effect:+.2f}%p 기여했습니다. 지역 요일 기준 기여는 별도이며 인과 효과가 아닙니다.",
            evidence_refs=["ev_demand_history"],
        ))
    remaining = float(sum(contributions[i] for i in range(len(FEATURES)) if i not in selected_indices)) * 100
    evidence.append(Evidence(evidence_id="ev_demand_other_factors", value_type="model_prediction", label="나머지 학습 입력 기여 합계",
                             display_value=f"{remaining:+.3f}%p", numeric_value=remaining, unit="percentage_points", source_refs=["src_demand_model"]))
    limitations = [*manifest["limitations"],
                  "D-30 조건으로 검증했으며 행사 직전 재예측도 같은 과거 이력을 사용합니다.",
                  "목표 인원·예산·출연진·실제 날씨는 학습하지 않았으므로 이 입력의 효과를 수요 수치로 주장하지 않습니다."]
    if outside:
        limitations.append("시군구 또는 일부 입력값이 실제 학습 범위를 벗어났습니다. 추가 근거를 확인해 주세요.")
    fingerprint = f"{manifest['model_version']}:{created.isoformat()}:{event_id}:{code}:{start_date}:{end_date}:{now.date()}"
    return AvailablePrediction(
        status="available", prediction_id="pred_demand_" + hashlib.sha256(fingerprint.encode()).hexdigest()[:24],
        event_id=event_id, prediction_type="regional_visit_demand", as_of=now,
        target_start_date=start_date, target_end_date=end_date, target_region=region,
        primary_metric=PredictionRangeMetric(metric_name="regional_visit_demand", unit="percent_change",
                                              p10=round(lower * 100, 3), p50=round(center * 100, 3), p90=round(upper * 100, 3)),
        components=[PredictionComponent(component_type="regional_baseline", value=100, unit="index_points",
                    scope_description="행사 직전28일 지역 일별 방문자 중앙값을100으로 정의한 비교 기준(향후 관측값; 인원수 미확정)", evidence_refs=["ev_demand_history"])],
        indicators=PredictionIndicators(congestion_level="unknown", ticket_demand_level="unknown"),
        confidence="low", data_sufficiency="limited", method="machine_learning", model_version=manifest["model_version"],
        factors=factors, evidence=evidence, sources=sources, limitations=limitations,
        out_of_distribution=outside, fallback_used=False, is_mock=False, created_at=now,
    )
