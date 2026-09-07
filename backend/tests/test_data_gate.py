import asyncio
import json
from pathlib import Path

import httpx
import pytest

from app.data_gate.client import DataGateError, PaginatedPublicDataClient
from app.data_gate.pipeline import (
    assert_no_post_event_features,
    build_quality_report,
    import_visitor_csv,
    normalize_festivals,
    read_jsonl_pages,
)


FIXTURES = Path(__file__).parent / "fixtures" / "data_gate"


def test_tourapi_legal_region_parts_join_to_visitor_sigungu_code() -> None:
    rows = normalize_festivals([
        {
            "contentid": "f-current",
            "title": "현재 스키마 행사",
            "eventstartdate": "20250501",
            "eventenddate": "20250502",
            "lDongRegnCd": "11",
            "lDongSignguCd": "215",
        }
    ])
    assert rows[0]["region_code"] == "11215"


def test_pipeline_joins_region_and_dates_without_claiming_attendance() -> None:
    festivals = read_jsonl_pages(FIXTURES / "festivals.jsonl")
    visitors = import_visitor_csv(FIXTURES / "visitors.csv")
    report, joined = build_quality_report(festivals, visitors)
    assert report["festival_rows_valid"] == 2
    assert report["joined_rows"] == 1
    assert report["gate_passed"] is False
    assert joined[0]["uplift_rate"] == 0.3
    assert "특정 축제 관람객 수가 아니" in report["interpretation"]


def test_pipeline_removes_duplicate_events_before_join() -> None:
    festivals = read_jsonl_pages(FIXTURES / "festivals.jsonl")
    visitors = import_visitor_csv(FIXTURES / "visitors.csv")
    report, joined = build_quality_report([*festivals, *festivals], visitors)
    assert report["festival_rows_raw"] == 4
    assert report["festival_rows_valid"] == 2
    assert report["duplicate_rate"] == 0.5
    assert len(joined) == 1


def test_post_event_feature_is_rejected() -> None:
    assert_no_post_event_features(["region_code", "month", "venue_capacity"])
    with pytest.raises(ValueError, match="actual_attendance"):
        assert_no_post_event_features(["region_code", "actual_attendance"])


def test_paginated_client_distinguishes_quota_and_empty_result() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, json={})
        return httpx.Response(200, json={"response": {"header": {"resultCode": "0000"}, "body": {"totalCount": 0, "items": ""}}})

    client = PaginatedPublicDataClient(max_retries=1, request_interval_seconds=0, transport=httpx.MockTransport(handler))
    page = asyncio.run(client.fetch_page("https://example.test", {}, 1, 100))
    assert page.items == []
    assert calls == 2


def test_paginated_client_reports_permission_error() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": {"header": {"resultCode": "20", "resultMsg": "ACCESS DENIED"}, "body": {}}})

    client = PaginatedPublicDataClient(transport=httpx.MockTransport(handler))
    with pytest.raises(DataGateError) as caught:
        asyncio.run(client.fetch_page("https://example.test", {}, 1, 100))
    assert caught.value.reason == "permission"
