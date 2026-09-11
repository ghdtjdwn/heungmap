from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import pytest

from scripts.evaluate_demand_model_v2 import (
    LABEL,
    build_error_analysis,
    chronological_split,
    engineer_features,
    regularized_region_mean_baseline,
    rolling_origin_splits,
)


def frame(rows: int = 60) -> pd.DataFrame:
    start = datetime(2025, 1, 1)
    records = []
    for index in range(rows):
        event_start = start + timedelta(days=index)
        duration = index % 3 + 1
        records.append(
            {
                "event_id": f"event-{index}",
                "start_timestamp": event_start,
                "end_date": int(
                    (event_start + timedelta(days=duration - 1)).strftime("%Y%m%d")
                ),
                "month": event_start.month,
                "day_of_week": event_start.weekday(),
                "duration_days": duration,
                "metro_code": "11",
                "region_code": "11110" if index % 2 else "11140",
                "latitude": 37.5,
                "longitude": 127.0,
                LABEL: index / 100,
            }
        )
    return pd.DataFrame(records)


def test_engineer_features_uses_only_event_schedule() -> None:
    engineered = engineer_features(frame(2))
    assert engineered.loc[0, "weekend_days"] == 0
    assert engineered.loc[0, "weekend_ratio"] == 0
    assert engineered.loc[0, "region_code_feature"] == "11140"
    assert engineered["day_of_year_sin"].between(-1, 1).all()
    assert engineered["day_of_year_cos"].between(-1, 1).all()


def test_chronological_split_keeps_same_date_on_one_side() -> None:
    data = frame()
    duplicate = data.iloc[[30]].assign(event_id="same-date")
    train, test = chronological_split(pd.concat([data, duplicate], ignore_index=True))
    assert train["start_timestamp"].max() < test["start_timestamp"].min()


def test_rolling_origin_splits_only_train_on_past_dates() -> None:
    splits = rolling_origin_splits(frame())
    assert len(splits) == 3
    assert all(
        train["start_timestamp"].max() < test["start_timestamp"].min()
        for train, test in splits
    )


def test_regularized_region_mean_shrinks_small_regions() -> None:
    train = pd.DataFrame(
        {
            "region_code": ["A", "A", "B"],
            LABEL: [0.0, 0.2, 1.0],
        }
    )
    test = pd.DataFrame({"region_code": ["A", "B", "C"]})
    prediction = regularized_region_mean_baseline(train, test, prior_weight=1.0)
    global_mean = train[LABEL].mean()
    assert prediction.iloc[0] == pytest.approx((0.1 * 2 + global_mean) / 3)
    assert prediction.iloc[1] == pytest.approx((1.0 + global_mean) / 2)
    assert prediction.iloc[2] == pytest.approx(global_mean)


def test_regularized_region_mean_rejects_negative_prior() -> None:
    with pytest.raises(ValueError, match="prior_weight"):
        regularized_region_mean_baseline(frame(), frame(1), prior_weight=-1)


def test_error_analysis_reports_period_region_label_and_worst_rows() -> None:
    test = frame(3)
    reference = pd.Series([0.0, 0.0, 0.0])
    candidate = pd.Series([0.0, 0.02, 0.5])

    analysis = build_error_analysis(test, reference, candidate)

    assert analysis["interpretation"].startswith("실제 축제 관람객 오차가 아니라")
    assert sum(item["rows"] for item in analysis["by_start_month"]) == 3
    assert sum(item["rows"] for item in analysis["by_metro_code"]) == 3
    assert sum(item["rows"] for item in analysis["by_actual_label_band"]) == 3
    assert analysis["largest_candidate_absolute_errors"][0]["event_id"] == "event-2"
    assert analysis["largest_candidate_absolute_errors"][0][
        "candidate_absolute_error"
    ] == pytest.approx(0.48)
