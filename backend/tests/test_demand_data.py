from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.demand.data import (
    FEATURES,
    HISTORY_DAYS,
    InsufficientHistoryError,
    build_training_dataset,
    load_daily_history,
    load_daily_visitors,
    make_features,
    save_daily_history,
)


def write_page(path: Path, items: list[dict]) -> Path:
    path.write_text(json.dumps({
        "retrieved_at": "2025-09-01T00:00:00+09:00", "items": items,
    }) + "\n", encoding="utf-8")
    return path


def visitor_rows(start: str = "2025-01-01", end: str = "2025-08-31") -> list[dict]:
    return [{
        "baseYmd": day.strftime("%Y%m%d"), "signguCode": "11110", "signguNm": "가상 지역",
        "touDivCd": str(visitor_type), "touNum": 100.0 if day.dayofweek < 5 else 120.0,
    } for day in pd.date_range(start, end) for visitor_type in range(1, 4)]


def festival(event_id: str = "synthetic-1", start: str = "20250701", end: str = "20250703") -> dict:
    return {
        "contentid": event_id, "title": "가상 축제", "eventstartdate": start, "eventenddate": end,
        "lDongRegnCd": "11", "lDongSignguCd": "110",
    }


def history_frame() -> pd.DataFrame:
    days = pd.date_range("2025-01-01", "2025-08-31")
    return pd.DataFrame({
        "date": days, "region_code": "11110", "region_name": "가상 지역",
        "visitor_count": np.where(days.dayofweek < 5, 300.0, 360.0),
        "retrieved_at": "2025-09-01T00:00:00+09:00",
    })


def test_duplicate_sources_do_not_double_counts_and_partial_days_are_discarded(tmp_path):
    rows = visitor_rows("2025-01-01", "2025-01-02")[:-1]
    path = write_page(tmp_path / "visitors.jsonl", rows + [rows[0]])
    daily, audit = load_daily_visitors([path, path])
    assert len(daily) == 1
    assert daily.iloc[0].visitor_count == 300
    assert daily.iloc[0].region_name == "가상 지역"
    assert audit["duplicate_type_rows_removed"] == 7
    assert audit["incomplete_type_days_discarded"] == 1


def test_conflicting_observation_cannot_be_silently_summed(tmp_path):
    rows = visitor_rows("2025-01-01", "2025-01-01")
    path = write_page(tmp_path / "visitors.jsonl", rows + [{**rows[0], "touNum": 101}])
    with pytest.raises(ValueError, match="충돌"):
        load_daily_visitors([path])


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), "not-a-number"])
def test_invalid_visitor_count_rejected(tmp_path, value):
    rows = visitor_rows("2025-01-01", "2025-01-01")
    rows[0]["touNum"] = value
    with pytest.raises(ValueError, match="유한한 비음수"):
        load_daily_visitors([write_page(tmp_path / "visitors.jsonl", rows)])


def test_future_observations_cannot_change_features():
    history = history_frame()
    expected = make_features("2025-07-01", "2025-07-03", "11110", history)
    cutoff = pd.Timestamp("2025-07-01") - pd.Timedelta(days=60)
    poisoned = history.copy()
    poisoned.loc[poisoned.date > cutoff, "visitor_count"] = 999999999
    assert make_features("2025-07-01", "2025-07-03", "11110", poisoned) == expected
    assert set(expected) == set(FEATURES)
    assert expected["calendar_expected_uplift"] == pytest.approx(0)
    assert expected["history_weekend_ratio"] == pytest.approx(1.2)
    assert sum(expected[f"weekday_{day}_fraction"] for day in range(7)) == pytest.approx(1)


def test_history_window_requires_every_day_and_includes_cutoff():
    history = history_frame()
    cutoff = pd.Timestamp("2025-07-01") - pd.Timedelta(days=60)
    missing_cutoff = history.loc[history.date != cutoff]
    with pytest.raises(InsufficientHistoryError, match="84일"):
        make_features("2025-07-01", "2025-07-03", "11110", missing_cutoff)
    oldest = cutoff - pd.Timedelta(days=HISTORY_DAYS - 1)
    missing_oldest = history.loc[history.date != oldest]
    with pytest.raises(InsufficientHistoryError):
        make_features("2025-07-01", "2025-07-03", "11110", missing_oldest)


@pytest.mark.parametrize("start,end", [("2025-07-02", "2025-07-01"), ("2025-07-01", "2025-07-31")])
def test_unsupported_event_windows_rejected(start, end):
    with pytest.raises(ValueError, match="1~30일"):
        make_features(start, end, "11110", history_frame())


def test_raw_dataset_label_and_prediction_availability_and_window_dedup(tmp_path):
    events = [festival(), festival(), festival("synthetic-2"), festival("long", end="20250831")]
    frame, daily, audit = build_training_dataset(
        [write_page(tmp_path / "festivals.jsonl", events)],
        [write_page(tmp_path / "visitors.jsonl", visitor_rows())],
    )
    assert len(frame) == 1
    row = frame.iloc[0]
    assert row.uplift_rate == pytest.approx(0)
    assert row.prediction_as_of == pd.Timestamp("2025-06-01")
    assert row.history_cutoff == pd.Timestamp("2025-05-02")
    assert row.label_available_date == pd.Timestamp("2025-08-02")
    assert json.loads(row.source_event_ids) == ["synthetic-1", "synthetic-2"]
    assert audit["excluded"]["duplicate_event_occurrences"] == 1
    assert audit["excluded"]["unsupported_duration"] == 1
    assert audit["identical_region_windows_removed"] == 1
    assert audit["historical_snapshot_verified"] is False
    assert daily.date.max() == pd.Timestamp("2025-08-31")


def test_partial_label_baseline_cannot_be_used(tmp_path):
    rows = [row for row in visitor_rows() if row["baseYmd"] != "20250630"]
    with pytest.raises(ValueError, match="행사 표본"):
        build_training_dataset(
            [write_page(tmp_path / "festivals.jsonl", [festival()])],
            [write_page(tmp_path / "visitors.jsonl", rows)],
        )


def test_history_save_load_roundtrip_and_corruption(tmp_path):
    history = history_frame()
    path = tmp_path / "history.csv"
    save_daily_history(history, path)
    loaded = load_daily_history(path)
    pd.testing.assert_frame_equal(loaded, history)
    save_daily_history(pd.concat([history, history.iloc[:1]]), path)
    with pytest.raises(ValueError, match="품질 검증"):
        load_daily_history(path)
