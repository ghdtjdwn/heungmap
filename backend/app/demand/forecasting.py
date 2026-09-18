"""D-30 시점에 이용 가능한 자료만 쓰는 시군구 일별 방문수요 예측."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor


LEAD_DAYS = 30
PUBLICATION_LAG_DAYS = 30
FEATURE_VERSION = "regional-daily-d30-v1"
FEATURES = [
    "log_baseline", "log_annual_growth", "log_recent_to_annual", "recent_trend",
    "recent_volatility", "lag60_to_baseline", "lag67_to_baseline", "lag74_to_baseline",
    "month_sin", "month_cos", *[f"weekday_{day}" for day in range(7)],
]
CANDIDATES = (
    {"num_leaves": 7, "min_child_samples": 120, "n_estimators": 180, "learning_rate": 0.025, "model_weight": 0.25},
    {"num_leaves": 11, "min_child_samples": 120, "n_estimators": 180, "learning_rate": 0.025, "model_weight": 0.4},
    {"num_leaves": 15, "min_child_samples": 120, "n_estimators": 200, "learning_rate": 0.025, "model_weight": 0.4},
)


def default_split_dates(data_end) -> tuple[str, str]:
    """자료 마지막 날로 (validation_start, test_start)를 정한다. 사람이 날짜를 고르지 않게 고정한 규칙이다.

    시험 구간은 data_end가 속한 달 1일부터다. 그 달 관측이 15일 미만이면 시험 표본이 너무 작으므로 앞 달 1일로
    당긴다. 후보 선택은 시험 직전 두 달의 전진 검증창이므로 validation_start는 시험 1개월 전이다.
    """
    end = pd.Timestamp(data_end).normalize()
    test_start = end.replace(day=1) if end.day >= 15 else (end.replace(day=1) - pd.offsets.MonthBegin(1))
    return (test_start - pd.offsets.MonthBegin(1)).date().isoformat(), test_start.date().isoformat()


class InsufficientForecastHistory(ValueError):
    """예측일에 필요한 정확 날짜 이력이 없을 때 사용한다."""


def make_forecast_features(target_date, history: pd.DataFrame) -> tuple[dict[str, float], float]:
    """목표일 60일 전까지의 이력과 전년도 대응일만 사용해 한 날짜 입력을 만든다."""
    target = pd.Timestamp(target_date).normalize()
    source = history.copy()
    source["date"] = pd.to_datetime(source.date)
    if source.date.duplicated().any():
        raise ValueError("같은 지역의 날짜 이력이 중복됐습니다.")
    values = source.set_index("date").visitor_count.astype(float).sort_index()

    def value(days: int) -> float:
        date_key = target - pd.Timedelta(days=days)
        if date_key not in values.index or pd.isna(values.loc[date_key]):
            raise InsufficientForecastHistory("예측에 필요한 정확 날짜 이력이 없습니다.")
        return float(values.loc[date_key])

    cutoff = target - pd.Timedelta(days=LEAD_DAYS + PUBLICATION_LAG_DAYS)
    recent_dates = pd.date_range(end=cutoff, periods=28)
    previous_dates = pd.date_range(end=cutoff - pd.Timedelta(days=28), periods=28)
    if not set(recent_dates).issubset(values.index) or not set(previous_dates).issubset(values.index):
        raise InsufficientForecastHistory("최근 비교 이력이 연속적이지 않습니다.")
    recent = values.reindex(recent_dates)
    previous = values.reindex(previous_dates)
    annual_dates = recent_dates - pd.Timedelta(days=364)
    if not set(annual_dates).issubset(values.index):
        raise InsufficientForecastHistory("전년도 성장률 이력이 없습니다.")
    annual = values.reindex(annual_dates).to_numpy(dtype=float)
    if (annual <= 0).any() or (recent <= 0).any() or (previous <= 0).any():
        raise InsufficientForecastHistory("비율 계산에 필요한 이력이 양수가 아닙니다.")
    annual_growth = float(np.median(recent.to_numpy(dtype=float) / annual))
    seasonal = np.array([value(357), value(364), value(371)])
    baseline = float(np.median(seasonal) * annual_growth)
    recent_median, previous_median = float(recent.median()), float(previous.median())
    lag424 = value(424)
    if min(baseline, recent_median, previous_median, lag424) <= 0:
        raise InsufficientForecastHistory("기준선 계산에 필요한 이력이 양수가 아닙니다.")
    angle = 2 * np.pi * (target.month - 1) / 12
    inputs = {
        "log_baseline": float(np.log1p(baseline)), "log_annual_growth": float(np.log(annual_growth)),
        "log_recent_to_annual": float(np.log(recent_median / lag424)),
        "recent_trend": recent_median / previous_median - 1,
        "recent_volatility": float(recent.std(ddof=0) / recent.mean()),
        "lag60_to_baseline": value(60) / baseline, "lag67_to_baseline": value(67) / baseline,
        "lag74_to_baseline": value(74) / baseline, "month_sin": float(np.sin(angle)),
        "month_cos": float(np.cos(angle)),
        **{f"weekday_{day}": float(target.dayofweek == day) for day in range(7)},
    }
    if list(inputs) != FEATURES or not np.isfinite(list(inputs.values())).all():
        raise ValueError("일별 예측 입력이 유효하지 않습니다.")
    return inputs, baseline


def build_daily_forecast_dataset(daily: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    required = {"date", "region_code", "region_name", "visitor_count", "retrieved_at"}
    if not required.issubset(daily.columns):
        raise ValueError("일별 방문자 데이터 컬럼이 부족합니다.")
    rows = []
    excluded_regions = 0
    for region, source in daily.groupby("region_code"):
        source = source.copy()
        source["date"] = pd.to_datetime(source.date)
        source = source.sort_values("date").drop_duplicates("date", keep=False).set_index("date")
        calendar = pd.date_range(source.index.min(), source.index.max())
        values = source.visitor_count.astype(float).reindex(calendar)
        if (values.dropna() < 0).any():
            raise ValueError("방문자 수는 비음수여야 합니다.")
        frame = pd.DataFrame({"date": calendar, "target": values.to_numpy()})
        for lag in (60, 67, 74, 81, 357, 364, 371, 424):
            frame[f"lag{lag}"] = values.shift(lag).to_numpy()
        annual_ratio = values / values.shift(364).replace(0, np.nan)
        frame["annual_growth"] = annual_ratio.rolling(28, min_periods=21).median().shift(60).to_numpy()
        frame["recent_median"] = values.rolling(28, min_periods=28).median().shift(60).to_numpy()
        frame["previous_median"] = values.rolling(28, min_periods=28).median().shift(88).to_numpy()
        frame["recent_mean"] = values.rolling(28, min_periods=28).mean().shift(60).to_numpy()
        frame["recent_std"] = values.rolling(28, min_periods=28).std(ddof=0).shift(60).to_numpy()
        seasonal = frame[["lag357", "lag364", "lag371"]].median(axis=1, skipna=False)
        frame["baseline"] = seasonal * frame.annual_growth
        valid = frame.dropna().copy()
        valid = valid.loc[(valid.target > 0) & (valid.baseline > 0) & (valid.recent_median > 0) & (valid.previous_median > 0)]
        if valid.empty:
            excluded_regions += 1
            continue
        angle = 2 * np.pi * (valid.date.dt.month - 1) / 12
        result = pd.DataFrame({
            "date": valid.date, "region_code": str(region), "region_name": source.region_name.dropna().iloc[-1],
            "target": valid.target, "baseline": valid.baseline,
            "history_cutoff": valid.date - pd.Timedelta(days=LEAD_DAYS + PUBLICATION_LAG_DAYS),
            "log_residual": np.log1p(valid.target) - np.log1p(valid.baseline),
            "log_baseline": np.log1p(valid.baseline),
            "log_annual_growth": np.log(valid.annual_growth),
            "log_recent_to_annual": np.log(valid.recent_median / valid.lag424),
            "recent_trend": valid.recent_median / valid.previous_median - 1,
            "recent_volatility": valid.recent_std / valid.recent_mean,
            "lag60_to_baseline": valid.lag60 / valid.baseline,
            "lag67_to_baseline": valid.lag67 / valid.baseline,
            "lag74_to_baseline": valid.lag74 / valid.baseline,
            "month_sin": np.sin(angle), "month_cos": np.cos(angle),
        })
        for day in range(7):
            result[f"weekday_{day}"] = (valid.date.dt.dayofweek == day).astype(float)
        rows.append(result)
    if not rows:
        raise ValueError("D-30 일별 예측 학습행을 만들 수 없습니다.")
    output = pd.concat(rows, ignore_index=True).replace([np.inf, -np.inf], np.nan).dropna()
    if output.empty or not np.isfinite(output[FEATURES + ["target", "baseline", "log_residual"]]).all().all():
        raise ValueError("일별 예측 학습값이 유효하지 않습니다.")
    return output.sort_values(["date", "region_code"]).reset_index(drop=True), {
        "feature_version": FEATURE_VERSION, "rows": len(output), "regions": int(output.region_code.nunique()),
        "date_min": output.date.min().date().isoformat(), "date_max": output.date.max().date().isoformat(),
        "excluded_regions": excluded_regions, "lead_days": LEAD_DAYS, "publication_lag_days": PUBLICATION_LAG_DAYS,
        "limitations": [
            "시군구 전체 방문자-일 수요이며 특정 축제 관람객이나 축제의 인과효과가 아닙니다.",
            "공표 지연을 30일로 가정해 목표일 60일 전까지의 관측만 사용합니다.",
            "연간 비교를 위해 2025년 1월 이후 이력이 완전한 지역만 평가합니다.",
        ],
    }


def _fit(frame: pd.DataFrame, parameters: dict[str, Any], alpha: float | None = None):
    arguments = dict(
        objective="quantile" if alpha is not None else "regression_l1", num_leaves=parameters["num_leaves"],
        min_child_samples=parameters["min_child_samples"], n_estimators=parameters["n_estimators"],
        learning_rate=parameters["learning_rate"], reg_lambda=2.0, verbosity=-1, random_state=42,
        n_jobs=1, deterministic=True, force_col_wise=True,
    )
    if alpha is not None:
        arguments["alpha"] = alpha
    return LGBMRegressor(**arguments).fit(frame[FEATURES], frame.log_residual)


def _predict(model, frame: pd.DataFrame, parameters: dict[str, Any]) -> np.ndarray:
    residual = model.predict(frame[FEATURES]) * parameters["model_weight"]
    return np.maximum(0, np.expm1(np.log1p(frame.baseline.to_numpy()) + residual))


def metrics(actual, predicted) -> dict[str, float | int]:
    actual, predicted = np.asarray(actual, float), np.asarray(predicted, float)
    return {
        "n": len(actual), "mae_people": float(np.mean(np.abs(actual - predicted))),
        "wape": float(np.abs(actual - predicted).sum() / actual.sum()),
        "median_ape": float(np.median(np.abs(actual - predicted) / actual)),
        "rmsle": float(np.sqrt(np.mean((np.log1p(actual) - np.log1p(predicted)) ** 2))),
        "within_20_percent": float(np.mean(np.abs(actual - predicted) / actual <= 0.2)),
    }


def evaluate_daily_forecast(frame: pd.DataFrame, *, validation_start="2026-06-01", test_start="2026-07-01"):
    validation_start, test_start = pd.Timestamp(validation_start), pd.Timestamp(test_start)
    train = frame.loc[frame.date < validation_start]
    validation = frame.loc[(frame.date >= validation_start) & (frame.date < test_start)]
    test = frame.loc[frame.date >= test_start]
    if min(len(train), len(validation), len(test)) == 0:
        raise ValueError("시간 분할의 학습·검증·시험 구간이 비었습니다.")
    # 한 달의 우연한 패턴에 맞추지 않도록 5월·6월 두 개의 전진 검증창에서 후보를 고른다.
    prior_start = validation_start - pd.offsets.MonthBegin(1)
    rolling_windows = [(prior_start, validation_start), (validation_start, test_start)]
    candidates = []
    for parameters in CANDIDATES:
        actual_parts, prediction_parts = [], []
        fold_metrics = []
        for fold_start, fold_end in rolling_windows:
            fold_train = frame.loc[frame.date < fold_start]
            fold_validation = frame.loc[(frame.date >= fold_start) & (frame.date < fold_end)]
            if min(len(fold_train), len(fold_validation)) == 0:
                raise ValueError("전진 검증창에 필요한 표본이 없습니다.")
            fold_model = _fit(fold_train, parameters)
            fold_prediction = _predict(fold_model, fold_validation, parameters)
            actual_parts.append(fold_validation.target.to_numpy())
            prediction_parts.append(fold_prediction)
            fold_metrics.append({"start": fold_start.date().isoformat(), "end": (fold_end - pd.Timedelta(days=1)).date().isoformat(),
                                 **metrics(fold_validation.target, fold_prediction)})
        combined_metrics = metrics(np.concatenate(actual_parts), np.concatenate(prediction_parts))
        candidates.append({"parameters": parameters, "metrics": combined_metrics, "folds": fold_metrics})
    selected = min(candidates, key=lambda item: (item["metrics"]["wape"], item["metrics"]["rmsle"]))
    development = frame.loc[frame.date < test_start]
    models = (_fit(development, selected["parameters"], 0.1), _fit(development, selected["parameters"]),
              _fit(development, selected["parameters"], 0.9))
    predictions = [_predict(model, test, selected["parameters"]) for model in models]
    # 선택된 중앙 모델의 전진 검증 오차로 80% 구간을 보정한다.
    calibration_train = frame.loc[frame.date < validation_start]
    calibration_model = _fit(calibration_train, selected["parameters"])
    calibration_prediction = _predict(calibration_model, validation, selected["parameters"])
    calibration_error = np.log1p(validation.target.to_numpy()) - np.log1p(calibration_prediction)
    # 시간 이동에도 과도하게 좁아지지 않도록 절대 로그오차의 80% split-conformal 폭을 사용한다.
    calibration_width = float(np.quantile(np.abs(calibration_error), 0.8, method="higher"))
    calibration_quantiles = np.array([-calibration_width, calibration_width])
    center_log = np.log1p(predictions[1])
    predictions[0] = np.maximum(0, np.expm1(center_log + calibration_quantiles[0]))
    predictions[2] = np.maximum(predictions[1], np.expm1(center_log + calibration_quantiles[1]))
    actual, baseline = test.target.to_numpy(), test.baseline.to_numpy()
    model_metrics, baseline_metrics = metrics(actual, predictions[1]), metrics(actual, baseline)
    checks = {
        "beats_seasonal_growth_wape": model_metrics["wape"] < baseline_metrics["wape"],
        "beats_seasonal_growth_rmsle": model_metrics["rmsle"] < baseline_metrics["rmsle"],
        "median_ape_below_10pct": model_metrics["median_ape"] < 0.10,
        "within_20pct_at_least_75pct": model_metrics["within_20_percent"] >= 0.75,
        "interval_80_coverage_at_least_75pct": float(np.mean((actual >= predictions[0]) & (actual <= predictions[2]))) >= 0.75,
    }
    report = {
        "schema_version": "1.0", "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_version": "regional-daily-1.0", "target": "시군구 일별 방문자-일 수(명)",
        "split": {"train_end": train.date.max().date().isoformat(), "validation_start": validation_start.date().isoformat(),
                  "validation_end": validation.date.max().date().isoformat(), "test_start": test_start.date().isoformat(),
                  "test_end": test.date.max().date().isoformat(), "training_rows": len(train),
                  "validation_rows": len(validation), "test_rows": len(test)},
        "candidate_selection": candidates, "selected_candidate": selected,
        "calibration_log_error_quantiles": calibration_quantiles.tolist(),
        "time_holdout": {"model": model_metrics, "seasonal_growth_baseline": baseline_metrics,
                         "wape_improvement": 1 - model_metrics["wape"] / baseline_metrics["wape"]},
        "interval_80_coverage": float(np.mean((actual >= predictions[0]) & (actual <= predictions[2]))),
        "adoption_checks": checks, "model_adopted": all(checks.values()),
        "rejection_reasons": [name for name, passed in checks.items() if not passed],
        "limitations": [
            "지역 전체 방문자-일 수요이며 특정 축제 관람객 수나 실제 현장 혼잡도가 아닙니다.",
            f"{test_start.date().isoformat()} 이후 시험구간은 모델 후보 선택에 사용하지 않았습니다.",
            "30일 공표 지연 가정은 과거 API snapshot이 없어 후향적으로 적용했습니다.",
        ],
    }
    output = test[["date", "region_code", "region_name", "target", "baseline"]].copy()
    output[["p10", "p50", "p90"]] = np.column_stack(predictions)
    return report, models, output


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def save_daily_run(output_dir: Path, report, models, predictions, frame, daily, audit, source_paths):
    output_dir.mkdir(parents=True, exist_ok=False)
    for name, model in zip(("p10", "p50", "p90"), models):
        model.booster_.save_model(str(output_dir / f"{name}.txt"))
    predictions.to_csv(output_dir / "holdout-predictions.csv", index=False)
    frame.to_csv(output_dir / "training.csv", index=False)
    daily.to_csv(output_dir / "history.csv", index=False)
    material = "".join(file_digest(output_dir / name) for name in ("p10.txt", "p50.txt", "p90.txt", "history.csv"))
    report["model_version"] += "-" + hashlib.sha256(material.encode()).hexdigest()[:12]
    report["data_audit"] = audit
    (output_dir / "evaluation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": "1.0", "model_version": report["model_version"], "created_at": report["generated_at"],
        "model_adopted": report["model_adopted"], "features": FEATURES,
        "parameters": report["selected_candidate"]["parameters"],
        "calibration_log_error_quantiles": report["calibration_log_error_quantiles"],
        "data_end": pd.to_datetime(daily.date).max().date().isoformat(),
        "regions": [{"code": str(code), "name": group.region_name.iloc[-1]}
                    for code, group in daily.loc[daily.region_code.astype(str).isin(set(frame.region_code.astype(str)))].groupby("region_code")],
        "source_files": [{"name": path.name, "sha256": file_digest(path)} for path in source_paths],
        "files": {name: file_digest(output_dir / name) for name in ("p10.txt", "p50.txt", "p90.txt", "history.csv", "evaluation.json")},
        "limitations": report["limitations"],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
