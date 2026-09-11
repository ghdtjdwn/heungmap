from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.compose import ColumnTransformer
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from app.data_gate.pipeline import assert_no_post_event_features
from scripts.evaluate_demand_model import (
    LABEL,
    metrics,
    prepare_frame,
    region_median_baseline,
)


@dataclass(frozen=True)
class CandidateSpec:
    name: str
    description: str
    objective: str
    categorical_features: tuple[str, ...]
    numeric_features: tuple[str, ...]

    @property
    def features(self) -> list[str]:
        return [*self.categorical_features, *self.numeric_features]


BASIC_NUMERIC_FEATURES = (
    "month",
    "day_of_week",
    "duration_days",
    "latitude",
    "longitude",
)
CALENDAR_NUMERIC_FEATURES = (
    *BASIC_NUMERIC_FEATURES,
    "day_of_year_sin",
    "day_of_year_cos",
    "weekend_days",
    "weekend_ratio",
    "starts_on_weekend",
    "ends_on_weekend",
)
CANDIDATES = (
    CandidateSpec(
        name="lightgbm_l2_basic",
        description="v1과 같은 기본 달력·광역·좌표 feature의 L2 LightGBM",
        objective="regression",
        categorical_features=("metro_code",),
        numeric_features=BASIC_NUMERIC_FEATURES,
    ),
    CandidateSpec(
        name="lightgbm_l1_calendar",
        description="MAE에 맞춘 L1 목적함수와 순환 날짜·주말 구성 feature",
        objective="regression_l1",
        categorical_features=("metro_code",),
        numeric_features=CALENDAR_NUMERIC_FEATURES,
    ),
    CandidateSpec(
        name="lightgbm_l1_calendar_region",
        description="L1 달력 모델에 기초지자체 범주를 추가하되 미관측 지역은 unknown 처리",
        objective="regression_l1",
        categorical_features=("metro_code", "region_code_feature"),
        numeric_features=CALENDAR_NUMERIC_FEATURES,
    ),
)


def engineer_features(frame: pd.DataFrame) -> pd.DataFrame:
    prepared = frame.copy()
    start = prepared["start_timestamp"]
    end = pd.to_datetime(prepared["end_date"].astype(str), format="%Y%m%d", errors="raise")
    day_of_year = start.dt.dayofyear
    weekend_days = [
        sum(day.weekday() >= 5 for day in pd.date_range(start_at, end_at))
        for start_at, end_at in zip(start, end, strict=True)
    ]
    prepared["day_of_year_sin"] = np.sin(2 * np.pi * day_of_year / 365.25)
    prepared["day_of_year_cos"] = np.cos(2 * np.pi * day_of_year / 365.25)
    prepared["weekend_days"] = weekend_days
    prepared["weekend_ratio"] = prepared["weekend_days"] / prepared["duration_days"]
    prepared["starts_on_weekend"] = (start.dt.dayofweek >= 5).astype(int)
    prepared["ends_on_weekend"] = (end.dt.dayofweek >= 5).astype(int)
    prepared["region_code_feature"] = prepared["region_code"].astype(str)
    return prepared


def chronological_split(
    frame: pd.DataFrame,
    train_fraction: float = 0.8,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not 0 < train_fraction < 1:
        raise ValueError("train_fraction은 0과 1 사이여야 합니다.")
    target_train_rows = len(frame) * train_fraction
    cumulative_rows = frame.groupby("start_timestamp").size().sort_index().cumsum()
    cutoff = min(cumulative_rows.items(), key=lambda item: abs(item[1] - target_train_rows))[0]
    train = frame[frame["start_timestamp"] <= cutoff].copy()
    test = frame[frame["start_timestamp"] > cutoff].copy()
    if train.empty or test.empty:
        raise ValueError("시간 분할 뒤 train과 test가 모두 필요합니다.")
    return train, test


def rolling_origin_splits(
    frame: pd.DataFrame,
    blocks: int = 5,
    minimum_train_blocks: int = 2,
) -> list[tuple[pd.DataFrame, pd.DataFrame]]:
    unique_dates = np.array(sorted(frame["start_timestamp"].unique()))
    if len(unique_dates) < blocks:
        raise ValueError("rolling validation에 필요한 고유 행사 날짜가 부족합니다.")
    date_blocks = [block for block in np.array_split(unique_dates, blocks) if len(block)]
    splits: list[tuple[pd.DataFrame, pd.DataFrame]] = []
    for test_block_index in range(minimum_train_blocks, len(date_blocks)):
        train_dates = np.concatenate(date_blocks[:test_block_index])
        test_dates = date_blocks[test_block_index]
        train = frame[frame["start_timestamp"].isin(train_dates)].copy()
        test = frame[frame["start_timestamp"].isin(test_dates)].copy()
        if not train.empty and not test.empty:
            splits.append((train, test))
    if not splits:
        raise ValueError("rolling validation split을 만들 수 없습니다.")
    return splits


def regularized_region_mean_baseline(
    train: pd.DataFrame,
    test: pd.DataFrame,
    prior_weight: float = 0.5,
) -> pd.Series:
    if prior_weight < 0:
        raise ValueError("prior_weight는 음수일 수 없습니다.")
    global_mean = float(train[LABEL].mean())
    region_stats = train.groupby("region_code")[LABEL].agg(["mean", "count"])
    regularized = (
        region_stats["mean"] * region_stats["count"] + global_mean * prior_weight
    ) / (region_stats["count"] + prior_weight)
    return test["region_code"].map(regularized).fillna(global_mean)


def build_model(spec: CandidateSpec) -> Pipeline:
    assert_no_post_event_features(spec.features)
    transform = ColumnTransformer(
        [
            (
                "category",
                OneHotEncoder(handle_unknown="ignore"),
                list(spec.categorical_features),
            ),
            ("number", "passthrough", list(spec.numeric_features)),
        ]
    )
    estimator = LGBMRegressor(
        objective=spec.objective,
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


def candidate_prediction(
    spec: CandidateSpec,
    train: pd.DataFrame,
    test: pd.DataFrame,
) -> np.ndarray:
    candidate = build_model(spec)
    candidate.fit(train[spec.features], train[LABEL])
    return candidate.predict(test[spec.features])


def improvement_rate(reference_mae: float, candidate_mae: float) -> float:
    if reference_mae == 0:
        return 0.0
    return (reference_mae - candidate_mae) / reference_mae


def evaluate_split(
    train: pd.DataFrame,
    test: pd.DataFrame,
    spec: CandidateSpec,
) -> dict[str, Any]:
    reference_metrics = metrics(test[LABEL], region_median_baseline(train, test))
    regularized_metrics = metrics(test[LABEL], regularized_region_mean_baseline(train, test))
    candidate_metrics = metrics(test[LABEL], candidate_prediction(spec, train, test))
    return {
        "train_rows": len(train),
        "test_rows": len(test),
        "train_end": train["start_timestamp"].max().date().isoformat(),
        "test_start": test["start_timestamp"].min().date().isoformat(),
        "test_end": test["start_timestamp"].max().date().isoformat(),
        "region_median_baseline": reference_metrics,
        "regularized_region_mean_baseline": regularized_metrics,
        "candidate": candidate_metrics,
        "candidate_mae_improvement_vs_region_median": round(
            improvement_rate(reference_metrics["mae"], candidate_metrics["mae"]), 6
        ),
    }


def rolling_candidate_results(
    splits: list[tuple[pd.DataFrame, pd.DataFrame]],
    spec: CandidateSpec,
) -> dict[str, Any]:
    folds = [
        {"fold": index, **evaluate_split(train, test, spec)}
        for index, (train, test) in enumerate(splits, start=1)
    ]
    reference_mean_mae = float(
        np.mean([fold["region_median_baseline"]["mae"] for fold in folds])
    )
    candidate_mean_mae = float(np.mean([fold["candidate"]["mae"] for fold in folds]))
    return {
        "folds": folds,
        "region_median_baseline_mean_mae": round(reference_mean_mae, 6),
        "candidate_mean_mae": round(candidate_mean_mae, 6),
        "candidate_mean_mae_improvement_rate": round(
            improvement_rate(reference_mean_mae, candidate_mean_mae), 6
        ),
    }


def unseen_region_results(frame: pd.DataFrame, spec: CandidateSpec) -> dict[str, Any]:
    fold_results: list[dict[str, Any]] = []
    splitter = GroupKFold(n_splits=min(5, frame["region_code"].nunique()))
    for fold, (train_indices, test_indices) in enumerate(
        splitter.split(frame, groups=frame["region_code"]), start=1
    ):
        train = frame.iloc[train_indices]
        test = frame.iloc[test_indices]
        global_median = np.repeat(float(train[LABEL].median()), len(test))
        candidate = candidate_prediction(spec, train, test)
        fold_results.append(
            {
                "fold": fold,
                "test_rows": len(test),
                "global_median_baseline": metrics(test[LABEL], global_median),
                "candidate": metrics(test[LABEL], candidate),
            }
        )
    baseline_mean_mae = float(
        np.mean([fold["global_median_baseline"]["mae"] for fold in fold_results])
    )
    candidate_mean_mae = float(np.mean([fold["candidate"]["mae"] for fold in fold_results]))
    return {
        "folds": fold_results,
        "global_median_baseline_mean_mae": round(baseline_mean_mae, 6),
        "candidate_mean_mae": round(candidate_mean_mae, 6),
        "candidate_mean_mae_improvement_rate": round(
            improvement_rate(baseline_mean_mae, candidate_mean_mae), 6
        ),
    }


def evaluate(frame: pd.DataFrame) -> dict[str, Any]:
    prepared = engineer_features(frame)
    outer_train, final_test = chronological_split(prepared)
    rolling_splits = rolling_origin_splits(outer_train)
    validation = {
        spec.name: rolling_candidate_results(rolling_splits, spec) for spec in CANDIDATES
    }
    selected_spec = min(
        CANDIDATES,
        key=lambda spec: validation[spec.name]["candidate_mean_mae"],
    )
    final_time = evaluate_split(outer_train, final_test, selected_spec)
    unseen_region = unseen_region_results(prepared, selected_spec)
    rolling_selected = validation[selected_spec.name]
    adoption_checks = {
        "at_least_two_event_years": prepared["start_timestamp"].dt.year.nunique() >= 2,
        "at_least_40_final_test_rows": len(final_test) >= 40,
        "rolling_mae_improves_by_10_percent": (
            rolling_selected["candidate_mean_mae_improvement_rate"] >= 0.10
        ),
        "final_time_mae_improves_by_10_percent": (
            final_time["candidate_mae_improvement_vs_region_median"] >= 0.10
        ),
        "final_time_rmse_not_worse": (
            final_time["candidate"]["rmse"]
            <= final_time["region_median_baseline"]["rmse"]
        ),
        "unseen_region_mae_not_worse": (
            unseen_region["candidate_mean_mae"]
            <= unseen_region["global_median_baseline_mean_mae"]
        ),
    }
    adopted = all(adoption_checks.values())
    return {
        "report_version": "2.0",
        "generated_at": datetime.now().astimezone().isoformat(),
        "target": {
            "name": "regional_daily_visitor_uplift_rate",
            "unit": "ratio_vs_prior_28d_median",
            "interpretation": "특정 축제 관람객 수가 아닌 행사 기간 기초지자체 방문수요의 상대 변화",
        },
        "selection_policy": (
            "마지막 20% 시간 구간은 후보 선택에 사용하지 않고, 앞선 80%의 rolling origin "
            "평균 MAE가 가장 낮은 고정 후보를 선택"
        ),
        "candidate_registry": {
            spec.name: {
                "description": spec.description,
                "objective": spec.objective,
                "features": spec.features,
            }
            for spec in CANDIDATES
        },
        "excluded_from_features": [
            "행사 기간 방문자 수와 label 파생값",
            "예측 시점 이후 검색·SNS·소비",
            "행사 직전 28일 방문자 중앙값: 먼 미래 기획 시점에는 알 수 없음",
            "다른 행사 수: 과거 시점별 TourAPI 공개 snapshot을 보존하지 않아 가용성 검증 전 제외",
        ],
        "data": {
            "rows": len(prepared),
            "event_years": sorted(
                prepared["start_timestamp"].dt.year.unique().astype(int).tolist()
            ),
            "regions": int(prepared["region_code"].nunique()),
            "outer_train_rows": len(outer_train),
            "final_test_rows": len(final_test),
        },
        "rolling_origin_training_validation": validation,
        "selected_candidate": selected_spec.name,
        "final_time_split": final_time,
        "unseen_region_group_cv": unseen_region,
        "adoption_checks": adoption_checks,
        "model_adopted": adopted,
        "rejection_reasons": [
            name for name, passed in adoption_checks.items() if not passed
        ],
        "shap_status": "computed" if adopted else "not_computed_model_not_adopted",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="지역 방문수요 모델의 rolling 선택·최종 시간·미관측 지역 검증"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/training-table-v1.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/model-evaluation-v2.json"),
    )
    args = parser.parse_args()
    report = evaluate(prepare_frame(args.input))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["model_adopted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
