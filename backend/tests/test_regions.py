from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from app.demand.data import splice_renamed_regions
from app.regions import RENAMED_REGION_CODES, predecessor_code, split_region_message, tour_area_for_legal_code
from app.schemas import RegionRef


def test_renamed_codes_are_one_to_one_and_map_back_to_gwangju_or_jeonnam():
    assert len(RENAMED_REGION_CODES) == len(set(RENAMED_REGION_CODES.values())) == 27
    assert tour_area_for_legal_code("12210") == "5" and tour_area_for_legal_code("12110") == "38"
    assert tour_area_for_legal_code("11110") is None and predecessor_code("12300") == "29170"


def test_splice_joins_old_history_to_new_code_and_prefers_new_on_overlap():
    rows = [("2026-06-29", "29110", 10.0), ("2026-06-30", "29110", 11.0), ("2026-06-30", "12210", 99.0),
            ("2026-07-01", "12210", 12.0), ("2026-07-01", "11110", 5.0)]
    daily = pd.DataFrame([{"date": pd.Timestamp(d), "region_code": c, "region_name": "동구" if c != "11110" else "종로구",
                           "visitor_count": v, "retrieved_at": "2026-09-18T00:00:00+09:00"} for d, c, v in rows])
    spliced, audit = splice_renamed_regions(daily)
    gwangju = spliced.loc[spliced.region_code == "12210"].set_index("date").visitor_count
    assert list(gwangju) == [10.0, 99.0, 12.0] and "29110" not in set(spliced.region_code)
    assert audit == {"renamed_regions_spliced": 1, "renamed_region_rows": 2, "renamed_region_overlap_dropped": 1}


def test_split_incheon_districts_get_an_honest_message():
    assert "새로 생겨" in split_region_message("28155") and "나뉘어" in split_region_message("28110")
    assert split_region_message("28710") is None


def test_gwangju_festival_summary_keeps_gwangju_area_after_reorganization():
    from app.services.tourapi import TourApiClient

    item = {"contentid": "1", "title": "광주비엔날레", "eventstartdate": "20260901", "eventenddate": "20261130",
            "lDongRegnCd": "12", "lDongSignguCd": "300", "addr1": "전남광주통합특별시 북구 비엔날레로 111"}
    summary = TourApiClient(service_key="x")._festival_to_summary(item, datetime(2026, 9, 18, tzinfo=ZoneInfo("Asia/Seoul")))
    assert summary.region.area_code == "5" and summary.region.legal_dong_code == "12300"


def test_mcst_lookup_uses_predecessor_province_for_unified_codes():
    from app.attendance.lookup import lookup_key, lookup_previous_attendance

    table = pd.DataFrame([{"plan_year": 2026, "province": "광주", "district": "북구", "title": "광주비엔날레",
                           "lookup_key": lookup_key("광주비엔날레"), "prior_attendance": 700000, "measurement": "계측"}])
    region = RegionRef(area_code="5", legal_dong_code="12300", display_name="전남광주통합특별시 북구")
    assert lookup_previous_attendance(title="제16회 광주비엔날레", region=region, table=table)["prior_attendance"] == 700000
