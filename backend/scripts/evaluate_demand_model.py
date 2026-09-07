from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.compose import ColumnTransformer
from sklearn.metrics import mean_absolute_error, median_absolute_error, root_mean_squared_error
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from app.data_gate.pipeline import assert_no_post_event_features


FEATURES = ["month", "day_of_week", "duration_days", "metro_code", "latitude", "longitude"]
CATEGORICAL_FEATURES = ["metro_code"]
NUMERIC_FEATURES = [feature for feature in FEATURES if feature not in CATEGORICAL_FEATURES]
LABEL = "uplift_rate"


def prepare_frame(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    required = {"start_date", "end_date", "region_code", "latitude", "longitude", LABEL}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"학습표 필수 열이 없습니다: {', '.join(missing)}")
    assert_no_post_event_features(FEATURES)
    start = pd.to_datetime(frame["start_date"].astype(str), format="%Y%m%d", errors="raise")
    end = pd.to_datetime(frame["end_date"].astype(str), format="%Y%m%d", errors="raise")
    prepared = frame.assign(
        month=start.dt.month,
        day_of_week=start.dt.dayofweek,
        duration_days=(end - start).dt.days + 1,
        metro_code=frame["region_code"].astype(str).str[:2],
        latitude=pd.to_numeric(frame["latitude"], errors="coerce"),
        longitude=pd.to_numeric(frame["longitude"], errors="coerce"),
        start_timestamp=start,
    )
    prepared = prepared.dropna(subset=[LABEL]).sort_values(["start_timestamp", "event_id"]).reset_index(drop=True)
    if len(prepared) < 50:
        raise ValueError("평가에는 label이 있는 행이 50개 이상 필요합니다.")
    return prepared


def model() -> Pipeline:
    transform = ColumnTransformer(
        [
            ("category", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
            ("number", "passthrough", NUMERIC_FEATURES),
        ]
    )
    estimator = LGBMRegressor(
        n_estimators=100,
        learning_rate=0.03,
        num_leaves=5,
        max_depth=3,
        min_child_samples=15,
        reg_lambda=1.0,
        verbosity=-1,
        random_state=42,
        n_jobs=1,
    )
    return Pipeline([("features", transform), ("regressor", estimator)])


def metrics(actual: pd.Series | np.ndarray, predicted: pd.Series | np.ndarray) -> dict[str, float]:
    return {
        "mae": round(float(mean_absolute_error(actual, predicted)), 6),
        "median_ae": round(float(median_absolute_error(actual, predicted)), 6),
        "rmse": round(float(root_mean_squared_error(actual, predicted)), 6),
    }


def region_median_baseline(train: pd.DataFrame, test: pd.DataFrame) -> pd.Series:
    global_median = float(train[LABEL].median())
    region_medians = train.groupby("region_code")[LABEL].median()
    return test["region_code"].map(region_medians).fillna(global_median)


def evaluate(frame: pd.DataFrame) -> dict[str, Any]:
    target_train_rows = len(frame) * 0.8
    cumulative_rows = frame.groupby("start_timestamp").size().sort_index().cumsum()
    cutoff = min(cumulative_rows.items(), key=lambda item: abs(item[1] - target_train_rows))[0]
    train = frame[frame["start_timestamp"] <= cutoff]
    test = frame[frame["start_timestamp"] > cutoff]
    baseline_prediction = region_median_baseline(train, test)
    candidate = model()
    candidate.fit(train[FEATURES], train[LABEL])
    candidate_prediction = candidate.predict(test[FEATURES])
    baseline_metrics = metrics(test[LABEL], baseline_prediction)
    model_metrics = metrics(test[LABEL], candidate_prediction)
    mae_improvement = (baseline_metrics["mae"] - model_metrics["mae"]) / baseline_metrics["mae"]

    group_fold_metrics: list[dict[str, Any]] = []
    splitter = GroupKFold(n_splits=min(5, frame["region_code"].nunique()))
    for fold, (train_indices, test_indices) in enumerate(
        splitter.split(frame, groups=frame["region_code"]), start=1
    ):
        group_train = frame.iloc[train_indices]
        group_test = frame.iloc[test_indices]
        fold_model = model()
        fold_model.fit(group_train[FEATURES], group_train[LABEL])
        fold_prediction = fold_model.predict(group_test[FEATURES])
        fold_baseline = np.repeat(float(group_train[LABEL].median()), len(group_test))
        group_fold_metrics.append(
            {
                "fold": fold,
                "test_rows": len(group_test),
                "baseline": metrics(group_test[LABEL], fold_baseline),
                "lightgbm": metrics(group_test[LABEL], fold_prediction),
            }
        )

    group_baseline_mae = float(np.mean([item["baseline"]["mae"] for item in group_fold_metrics]))
    group_model_mae = float(np.mean([item["lightgbm"]["mae"] for item in group_fold_metrics]))
    years = sorted(frame["start_timestamp"].dt.year.unique().astype(int).tolist())
    adoption_checks = {
        "at_least_two_event_years": len(years) >= 2,
        "at_least_40_time_test_rows": len(test) >= 40,
        "time_mae_improves_by_10_percent": mae_improvement >= 0.10,
        "time_rmse_not_worse": model_metrics["rmse"] <= baseline_metrics["rmse"],
        "unseen_region_mae_not_worse": group_model_mae <= group_baseline_mae,
    }
    adopted = all(adoption_checks.values())
    reasons = [name for name, passed in adoption_checks.items() if not passed]
    return {
        "report_version": "1.0",
        "generated_at": datetime.now().astimezone().isoformat(),
        "target": {
            "name": "regional_daily_visitor_uplift_rate",
            "unit": "ratio_vs_prior_28d_median",
            "interpretation": "특정 축제 관람객 수가 아닌 행사 기간 기초지자체 방문수요의 상대 변화",
        },
        "features": FEATURES,
        "excluded_from_features": [
            "행사 기간 방문자 수와 label 파생값",
            "예측 시점 이후 검색·SNS·소비",
            "행사 직전 28일 방문자 중앙값: 먼 미래 기획 시점에는 알 수 없음",
        ],
        "data": {
            "rows": len(frame),
            "event_years": years,
            "regions": int(frame["region_code"].nunique()),
            "train_rows": len(train),
            "test_rows": len(test),
            "train_end": train["start_timestamp"].max().date().isoformat(),
            "test_start": test["start_timestamp"].min().date().isoformat(),
            "test_end": test["start_timestamp"].max().date().isoformat(),
        },
        "time_split": {
            "baseline": baseline_metrics,
            "lightgbm": model_metrics,
            "mae_improvement_rate": round(mae_improvement, 6),
        },
        "unseen_region_group_cv": {
            "folds": group_fold_metrics,
            "baseline_mean_mae": round(group_baseline_mae, 6),
            "lightgbm_mean_mae": round(group_model_mae, 6),
        },
        "adoption_checks": adoption_checks,
        "model_adopted": adopted,
        "rejection_reasons": reasons,
        "shap_status": "computed" if adopted else "not_computed_model_not_adopted",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="지역 방문수요 label의 baseline·LightGBM 검증")
    parser.add_argument("--input", type=Path, default=Path("data/processed/training-table-v1.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/model-evaluation.json"))
    args = parser.parse_args()
    report = evaluate(prepare_frame(args.input))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["model_adopted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
