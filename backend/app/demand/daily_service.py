"""채택된 D-30 일별 지역 방문수요 artifact의 운영 adapter."""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from app.demand.service import ADMIN_TO_AREA
from app.regions import split_region_message, tour_area_for_legal_code
from app.schemas import (
    AvailablePrediction, Evidence, PredictionComponent, PredictionFactor, PredictionIndicators,
    PredictionRangeMetric, PredictionResult, RegionRef, SourceRef, UnavailablePrediction,
)


DEFAULT_DIRECTORY = Path(__file__).resolve().parents[3] / "data" / "processed" / "daily-forecast-production-v3"
STALE_AFTER_DAYS = 60
MAX_LEAD_DAYS = 30  # 오늘부터 30일 이내에 시작하는(또는 이미 진행 중인) 구간만 예측한다.
MAX_WINDOW_DAYS = 30
FEATURE_LABELS = {
    "log_baseline": "전년도 같은 시기 수요", "log_annual_growth": "지역 연간 성장률",
    "log_recent_to_annual": "최근·전년 지역수요 차이", "recent_trend": "최근 지역수요 추세",
    "recent_volatility": "최근 수요 변동성", "lag60_to_baseline": "60일 전 수요",
    "lag67_to_baseline": "67일 전 수요", "lag74_to_baseline": "74일 전 수요",
    "month_sin": "계절", "month_cos": "계절",
    **{f"weekday_{day}": f"{'월화수목금토일'[day]}요일" for day in range(7)},
}


def select_production_directory(root: Path) -> Path | None:
    """production-v* 중 번호가 가장 큰 채택 artifact. 미채택·손상 폴더는 건너뛴다(무결성은 _load가 다시 검사)."""
    candidates = []
    for path in root.glob("daily-forecast-production-v*"):
        match = re.fullmatch(r"daily-forecast-production-v(\d+)", path.name)
        if match and path.is_dir():
            candidates.append((int(match.group(1)), path))
    for _, path in sorted(candidates, reverse=True):
        try:
            manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
            report = json.loads((path / "evaluation.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if manifest.get("model_adopted") is True and report.get("model_adopted") is True:
            return path
    return None


def _directory() -> Path:
    """환경변수로 고정한 artifact가 우선이고, 없으면 가장 최근 채택 production 폴더를 쓴다."""
    if configured := os.environ.get("HEUNGMAP_DAILY_MODEL_DIR"):
        return Path(configured).resolve()
    return (select_production_directory(DEFAULT_DIRECTORY.parent) or DEFAULT_DIRECTORY).resolve()


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@lru_cache(maxsize=2)
def _load(directory: str, state: tuple):
    import lightgbm as lgb
    import numpy as np
    import pandas as pd
    from app.demand.forecasting import FEATURES

    root = Path(directory)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    expected = {"p10.txt", "p50.txt", "p90.txt", "history.csv", "evaluation.json"}
    if not isinstance(manifest, dict) or manifest.get("schema_version") != "1.0" or manifest.get("features") != FEATURES:
        raise ValueError("지원하지 않는 일별 모델 artifact입니다.")
    if set(manifest.get("files", {})) != expected:
        raise ValueError("일별 모델 artifact 파일 목록이 불완전합니다.")
    for name in expected:
        if _digest(root / name) != manifest["files"][name]:
            raise ValueError("일별 모델 artifact 무결성 검사에 실패했습니다.")
    report = json.loads((root / "evaluation.json").read_text(encoding="utf-8"))
    if manifest.get("model_adopted") is not True or report.get("model_adopted") is not True:
        raise ValueError("채택되지 않은 일별 모델입니다.")
    if not report.get("adoption_checks") or not all(report["adoption_checks"].values()):
        raise ValueError("일별 모델의 채택 검증이 불완전합니다.")
    if manifest.get("model_version") != report.get("model_version"):
        raise ValueError("일별 모델 버전이 일치하지 않습니다.")
    created = datetime.fromisoformat(manifest["created_at"])
    if created.tzinfo is None:
        raise ValueError("모델 생성시각에 시간대가 없습니다.")
    correction = np.asarray(manifest["calibration_log_error_quantiles"], dtype=float)
    if correction.shape != (2,) or not np.isfinite(correction).all() or correction[0] > 0 or correction[1] < 0:
        raise ValueError("예측구간 보정값이 잘못됐습니다.")
    models = [lgb.Booster(model_file=str(root / f"{name}.txt")) for name in ("p10", "p50", "p90")]
    if any(model.feature_name() != FEATURES for model in models):
        raise ValueError("저장 모델 입력 순서가 다릅니다.")
    history = pd.read_csv(root / "history.csv", dtype={"region_code": str}, parse_dates=["date"])
    if history.empty or not {"date", "region_code", "region_name", "visitor_count", "retrieved_at"}.issubset(history.columns):
        raise ValueError("모델 방문자 이력이 잘못됐습니다.")
    histories = {code: group.copy() for code, group in history.groupby("region_code")}
    return manifest, models, histories


def _artifact():
    directory = _directory()
    files = ("manifest.json", "p10.txt", "p50.txt", "p90.txt", "history.csv", "evaluation.json")
    state = tuple((name, (directory / name).stat().st_mtime_ns, (directory / name).stat().st_size) for name in files)
    return _load(str(directory), state)


def model_status(now: datetime | None = None) -> dict:
    """artifact를 검증해 불러오고 노후 여부를 계산한다. 파일 경로·비밀값은 노출하지 않는다."""
    now = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo("Asia/Seoul"))
    try:
        manifest, _, histories = _artifact()
        data_end = date.fromisoformat(manifest["data_end"])
        created = datetime.fromisoformat(manifest["created_at"])
    except OSError:
        return {"status": "unavailable", "adopted": False, "checked_at": now, "reason": "채택 모델 파일을 찾거나 읽을 수 없습니다."}
    except ImportError:
        return {"status": "unavailable", "adopted": False, "checked_at": now, "reason": "모델 실행 라이브러리를 불러오지 못했습니다."}
    except (ValueError, KeyError, TypeError) as exc:
        message = str(exc) if isinstance(exc, ValueError) else "모델 manifest 형식이 잘못됐습니다."
        return {"status": "unavailable", "adopted": False, "checked_at": now, "reason": message[:500]}
    except Exception:  # LightGBM 파일 파싱 오류 등. 상태 조회는 어떤 경우에도 500을 내지 않는다.
        return {"status": "unavailable", "adopted": False, "checked_at": now, "reason": "모델 파일을 해석하지 못했습니다."}
    remaining = STALE_AFTER_DAYS - (now.date() - data_end).days
    return {
        "status": "ready" if remaining >= 0 and created <= now else "stale", "adopted": True, "checked_at": now,
        "model_version": manifest["model_version"], "data_end": data_end, "created_at": created,
        "last_predictable_target_date": data_end + timedelta(days=STALE_AFTER_DAYS), "days_until_stale": remaining,
        "regions": len(prediction_regions(now)),  # 지금 선택·예측할 수 있는 시군구 수
    }


def area_code_for(code: str) -> str | None:
    """법정동 시군구 코드 → 공통 계약 지역 코드. 전남광주통합특별시는 옛 광주·전남 코드로 나눈다."""
    return tour_area_for_legal_code(code) or ADMIN_TO_AREA.get(code[:2])


def prediction_regions(now: datetime | None = None) -> list[RegionRef]:
    """지금 예측할 수 있는 시군구만 돌려준다. 이력이 오래전에 끊긴 지역(행정구역 개편 등)은 목록에서 뺀다."""
    today = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo("Asia/Seoul")).date()
    try:
        manifest, _, histories = _artifact()
        regions = []
        for item in manifest["regions"]:
            code = str(item["code"])
            area = area_code_for(code)
            if code not in histories or not area:
                continue
            if (today - histories[code].date.max().date()).days > STALE_AFTER_DAYS:
                continue
            regions.append(RegionRef(area_code=area, legal_dong_code=code, display_name=item["name"]))
        return sorted(regions, key=lambda item: (item.area_code, item.display_name))
    except (OSError, ValueError, KeyError, TypeError, ImportError):
        return []


def predict_rows(models, manifest: dict, frame, baselines):
    """저장 모델로 날짜별 입력을 예측해 (하한, 중앙, 상한, 로그 중앙) 일별 배열을 돌려준다."""
    import numpy as np

    raw = np.asarray(models[1].predict(frame[manifest["features"]], num_threads=1), dtype=float)
    center_log = np.log1p(np.asarray(baselines, dtype=float)) + raw * float(manifest["parameters"]["model_weight"])
    low_error, high_error = manifest["calibration_log_error_quantiles"]
    center = np.maximum(0, np.expm1(center_log))
    return (np.maximum(0, np.expm1(center_log + low_error)), center,
            np.maximum(center, np.expm1(center_log + high_error)), center_log)


LEVEL_LABELS = {"low": "낮음", "medium": "보통", "high": "높음", "very_high": "매우 높음"}


def region_confidence(manifest: dict, code: str) -> tuple[str, dict | None]:
    """이 시군구의 시간 홀드아웃 WAPE로 신뢰도를 정한다. 기준이 없는 이전 artifact는 기존 medium을 유지한다."""
    thresholds = manifest.get("confidence_thresholds")
    if not thresholds:
        return "medium", None
    meta = next((item for item in manifest["regions"] if str(item["code"]) == code), {})
    wape, days = meta.get("holdout_wape"), meta.get("holdout_days") or 0
    if wape is None or days < thresholds["min_holdout_days"]:
        return "low", None
    level = "high" if wape < thresholds["high_below"] else "medium" if wape < thresholds["medium_below"] else "low"
    return level, {"wape": float(wape), "days": int(days)}


def regional_demand_level(manifest: dict, history, cutoff: date, daily_mean: float) -> tuple[str, float | None]:
    """예측 일평균이 최근 1년 이 지역 관측 분포의 몇 백분위인지로 평소 대비 수요 수준을 정한다. 현장 혼잡이 아니다."""
    import pandas as pd

    percentiles = manifest.get("demand_level_percentiles")
    if not percentiles:
        return "unknown", None
    dates = pd.to_datetime(history.date)
    recent = history.loc[(dates > pd.Timestamp(cutoff) - pd.Timedelta(days=365)) & (dates <= pd.Timestamp(cutoff))]
    if len(recent) < percentiles["min_days"]:
        return "unknown", None
    percentile = float((recent.visitor_count.to_numpy(dtype=float) < daily_mean).mean() * 100)
    level = ("very_high" if percentile >= percentiles["very_high"] else "high" if percentile >= percentiles["high"]
             else "medium" if percentile >= percentiles["medium"] else "low")
    return level, percentile


def merged_factors(contributions, features: list[str], limit: int = 5) -> list[tuple[str, str, float]]:
    """같은 라벨(예: 계절 sin·cos)의 TreeSHAP 기여를 합쳐 (대표 feature, 라벨, 로그 기여) 상위 목록을 만든다."""
    merged: dict[str, tuple[str, float]] = {}
    for feature, value in zip(features, contributions):
        label = FEATURE_LABELS.get(feature, feature)
        first, total = merged.get(label, (feature, 0.0))
        merged[label] = (first, total + float(value))
    ranked = sorted(merged.items(), key=lambda item: abs(item[1][1]), reverse=True)[:limit]
    return [(feature, label, value) for label, (feature, value) in ranked]


def _unavailable(event_id, now, reason, message):
    return UnavailablePrediction(status="unavailable", event_id=event_id, reason_code=reason, message=message,
        as_of=now, sources=[], limitations=["지역 전체 방문자-일 수요이며 특정 축제 관람객 수가 아닙니다."],
        retryable=False, is_mock=False)


def predict_demand(*, event_id: str, start_date: date, end_date: date, region: RegionRef,
                   event_type: str, as_of: datetime | None = None) -> PredictionResult:
    import lightgbm as lgb
    import numpy as np
    import pandas as pd
    from app.demand.forecasting import FEATURES, InsufficientForecastHistory, make_forecast_features

    now = (as_of or datetime.now(timezone.utc))
    if now.tzinfo is None:
        raise ValueError("예측 기준시각에는 시간대가 필요합니다.")
    now = now.astimezone(ZoneInfo("Asia/Seoul"))
    if event_type not in {"festival", "local_event"}:
        return _unavailable(event_id, now, "unsupported_event_type", "축제·지역 행사만 지원합니다.")
    code = region.legal_dong_code if region else None
    if message := split_region_message(code):
        return _unavailable(event_id, now, "insufficient_data", message)
    if (not code or not re.fullmatch(r"\d{5}", code) or code.endswith("000")
            or region.area_code not in {area_code_for(code), code[:2]}):
        return _unavailable(event_id, now, "missing_required_input", "지원 시군구를 정확히 선택해 주세요.")
    today = now.date()
    if end_date < start_date:
        return _unavailable(event_id, now, "missing_required_input", "행사 종료일이 시작일보다 빠릅니다.")
    if end_date < today:
        return _unavailable(event_id, now, "insufficient_data", "이미 끝난 행사는 예측하지 않습니다.")
    window_start = max(start_date, today)
    if (window_start - today).days > MAX_LEAD_DAYS:
        return _unavailable(event_id, now, "insufficient_data", "행사 시작 30일 전부터 예측을 제공합니다.")
    try:
        manifest, models, histories = _artifact()
        if code not in histories:
            return _unavailable(event_id, now, "insufficient_data", "이 시군구는 검증된 학습 범위에 없습니다.")
        created = datetime.fromisoformat(manifest["created_at"])
        data_end = date.fromisoformat(manifest["data_end"])
        if created > now or (today - data_end).days > STALE_AFTER_DAYS:
            return _unavailable(event_id, now, "insufficient_data", "최신 방문자 이력으로 모델을 갱신해야 합니다.")
        # 진행 중인 행사는 남은 날짜만, 긴 행사는 최대 30일만, 자료로 계산 가능한 마지막 날까지만 예측한다.
        # 입력은 어느 날짜든 목표일 60일 전까지의 이력이므로 D-30 예측과 같은 정보 범위다.
        window_end = min(end_date, window_start + timedelta(days=MAX_WINDOW_DAYS - 1),
                         data_end + timedelta(days=STALE_AFTER_DAYS))
        if window_end < window_start:
            return _unavailable(event_id, now, "insufficient_data", "최신 방문자 이력으로 모델을 갱신해야 합니다.")
        history = histories[code]
        history = history[pd.to_datetime(history.retrieved_at, utc=True) <= now.astimezone(timezone.utc)]
        inputs, baselines = [], []
        for target in pd.date_range(window_start, window_end):
            values, baseline = make_forecast_features(target, history)
            inputs.append(values)
            baselines.append(baseline)
        frame = pd.DataFrame(inputs, columns=FEATURES)
        weight = float(manifest["parameters"]["model_weight"])
        daily_low, daily_center, daily_high, _ = predict_rows(models, manifest, frame, baselines)
        lower, center, upper = map(float, (daily_low.sum(), daily_center.sum(), daily_high.sum()))
        contributions = np.asarray(models[1].predict(frame, pred_contrib=True, num_threads=1), dtype=float).mean(axis=0) * weight
        if not np.isfinite([lower, center, upper, *contributions]).all():
            raise ValueError("예측값이 유한하지 않습니다.")
    except InsufficientForecastHistory:
        return _unavailable(event_id, now, "insufficient_data", "목표일 60일 전 기준 이력 또는 전년도 대응 이력이 부족합니다.")
    except (OSError, ValueError, KeyError, TypeError, ImportError, lgb.basic.LightGBMError):
        return _unavailable(event_id, now, "model_unavailable", "채택된 일별 수요 모델을 검증해 불러오지 못했습니다.")

    cutoff = window_end - timedelta(days=60)
    partial = (window_start, window_end) != (start_date, end_date)
    sources = [
        SourceRef(source_id="src_daily_model", source_type="heungmap_model", provider_name="흥할지도",
                  dataset_name=manifest["model_version"], retrieved_at=created,
                  limitation="2026년 8월 미래 홀드아웃을 통과한 지역 방문자-일 예측입니다."),
        SourceRef(source_id="src_daily_visitors", source_type="kto_datalab", provider_name="한국관광공사",
                  dataset_name="지역별 방문자수", source_url="https://www.data.go.kr/data/15101972/openapi.do",
                  retrieved_at=pd.to_datetime(history.retrieved_at, utc=True).max().to_pydatetime(),
                  data_as_of=datetime.combine(cutoff, datetime.min.time(), tzinfo=now.tzinfo),
                  limitation="이동통신 기반 지역 방문자-일 집계이며 고유 방문자나 축제 입장객이 아닙니다."),
    ]
    evidence = [Evidence(evidence_id="ev_daily_baseline", value_type="derived_value", label="계절·성장 기준선",
                         display_value=f"{'예측 구간' if partial else '행사기간'} 합계 {sum(baselines):,.0f} 방문자-일", numeric_value=float(sum(baselines)),
                         unit="people", source_refs=["src_daily_visitors"], as_of=sources[1].data_as_of,
                         limitation="전년도 같은 요일과 60일 전까지 관측한 연간 성장률로 계산했습니다.")]
    confidence, holdout = region_confidence(manifest, code)
    demand_level, percentile = regional_demand_level(manifest, history, cutoff, center / len(baselines))
    limitations = [*manifest["limitations"],
                   "행사기간 합계는 날짜별 방문자 수의 합으로 같은 사람이 여러 날 방문하면 중복될 수 있습니다.",
                   "예산·출연진·날씨·축제 자체 효과를 이 수치의 원인으로 해석하지 않습니다."]
    if partial:
        limitations.append(f"행사 전체 기간({start_date}~{end_date}) 중 {window_start}~{window_end} 구간만 예측했습니다. "
                           "지난 날짜, 30일을 넘는 날짜, 현재 자료로 계산할 수 없는 날짜는 포함하지 않습니다.")
    if holdout:
        evidence.append(Evidence(evidence_id="ev_daily_region_holdout", value_type="derived_value", label="이 시군구 시간 홀드아웃 오차",
            display_value=f"WAPE {holdout['wape']:.1%} ({holdout['days']}일)", numeric_value=holdout["wape"], unit="ratio",
            source_refs=["src_daily_model"], confidence=confidence,
            limitation="과거 시험 구간의 오차이며 이번 예측의 오차를 보장하지 않습니다. 신뢰도는 이 값으로 정했습니다."))
    if percentile is not None:
        evidence.append(Evidence(evidence_id="ev_daily_demand_level", value_type="derived_value", label="평소 대비 지역 방문수요 수준",
            display_value=f"최근 1년 이 지역 일별 방문자 중 {percentile:.0f}백분위 ({LEVEL_LABELS[demand_level]})",
            numeric_value=round(percentile, 1), unit="percentile", source_refs=["src_daily_visitors"], as_of=sources[1].data_as_of,
            limitation="예측 일평균을 최근 1년 관측 분포와 비교한 상대 수준이며 현장 혼잡도나 입장 대기가 아닙니다."))
        limitations.append("congestion_level은 최근 1년 지역 방문자 분포에서 예측 일평균의 위치이며 현장 혼잡이 아닙니다.")
    factors = []
    for feature, label, value in merged_factors(contributions, FEATURES):
        effect = float(np.expm1(value) * 100)
        factors.append(PredictionFactor(factor_id=f"daily_{feature}", label=label,
            direction="up" if effect > 0 else "down" if effect < 0 else "neutral", importance=abs(effect),
            explanation=f"LightGBM TreeSHAP 기여도 기준 지역 계절 기준선 대비 약 {effect:+.2f}%입니다. 인과효과는 아닙니다.",
            evidence_refs=["ev_daily_baseline"]))
    fingerprint = f"{manifest['model_version']}:{event_id}:{code}:{window_start}:{window_end}:{now.date()}"
    return AvailablePrediction(status="available", prediction_id="pred_daily_" + hashlib.sha256(fingerprint.encode()).hexdigest()[:24],
        event_id=event_id, prediction_type="regional_visit_demand", as_of=now,
        target_start_date=window_start, target_end_date=window_end, target_region=region,
        primary_metric=PredictionRangeMetric(metric_name="regional_visit_demand", unit="people",
                                             p10=round(lower), p50=round(center), p90=round(upper)),
        components=[PredictionComponent(component_type="regional_baseline", value=round(sum(baselines)), unit="people",
            scope_description=("예측 구간" if partial else "행사기간") + " 시군구 전체 예상 방문자-일 계절 기준선",
            evidence_refs=["ev_daily_baseline"])],
        indicators=PredictionIndicators(congestion_level=demand_level, ticket_demand_level="unknown"),
        confidence=confidence, data_sufficiency="sufficient", method="machine_learning", model_version=manifest["model_version"],
        factors=factors, evidence=evidence, sources=sources, limitations=limitations,
        out_of_distribution=False, fallback_used=False, is_mock=False, created_at=now)
