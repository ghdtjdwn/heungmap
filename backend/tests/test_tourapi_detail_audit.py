from __future__ import annotations

import pandas as pd
import pytest

from scripts.audit_tourapi_detail_features import (
    select_audit_sample,
    summarize_availability,
)


def test_sample_covers_each_metro_when_size_allows() -> None:
    frame = pd.DataFrame(
        {
            "event_id": [f"event-{index}" for index in range(12)],
            "region_code": ["11", "11", "26", "26", "41", "41"] * 2,
        }
    )

    sample = select_audit_sample(frame, sample_size=6)

    assert len(sample) == 6
    assert set(sample["metro_code"]) == {"11", "26", "41"}
    assert sample["event_id"].is_unique


def test_sample_rejects_missing_columns() -> None:
    with pytest.raises(ValueError, match="필수 열"):
        select_audit_sample(pd.DataFrame({"event_id": ["1"]}), sample_size=1)


def test_availability_uses_aliases_and_keeps_missingness_visible() -> None:
    records = [
        {
            "event_id": "1",
            "metro_code": "11",
            "common": [{"cat1": "A", "overview": "설명"}],
            "intro": [{"eventplace": "광장", "sponsor1": "기관"}],
        },
        {
            "event_id": "2",
            "metro_code": "26",
            "common": [{"lclsSystm1": "B", "overview": ""}],
            "intro": [],
        },
    ]

    report = summarize_availability(records, availability_threshold=0.75)

    assert report["sample"]["events"] == 2
    assert report["sample"]["metro_codes"] == 2
    assert report["feature_availability"]["category_primary"][
        "availability_rate"
    ] == 1
    assert report["feature_availability"]["category_primary"][
        "distinct_nonempty_values"
    ] == 2
    assert report["feature_availability"]["category_primary"][
        "dominant_value_rate"
    ] == 0.5
    assert report["feature_availability"]["overview"]["availability_rate"] == 0.5
    assert report["feature_availability"]["event_place"]["missing_rows"] == 1
    assert "category_primary" in report["candidates_passing_availability_gate"]
    assert "overview" not in report["candidates_passing_availability_gate"]
