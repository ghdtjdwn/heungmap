import pandas as pd

from app.attendance import lookup
from app.schemas import AvailablePrediction, RegionRef


TABLE = pd.DataFrame([
    {"plan_year": 2026, "province": "강원", "district": "강릉시", "title": "제20회 강릉단오제", "lookup_key": lookup.lookup_key("강릉단오제"), "prior_attendance": 956000, "measurement": "계측"},
    {"plan_year": 2026, "province": "강원", "district": "고성군", "title": "명태축제", "lookup_key": lookup.lookup_key("명태축제"), "prior_attendance": 1000, "measurement": "추정"},
    {"plan_year": 2026, "province": "경남", "district": "고성군", "title": "명태축제", "lookup_key": lookup.lookup_key("명태축제"), "prior_attendance": 2000, "measurement": "추정"},
    {"plan_year": 2026, "province": "서울", "district": "", "title": "2026년 서울세계도시문화축제", "lookup_key": lookup.lookup_key("2026년 서울세계도시문화축제"), "prior_attendance": 160000, "measurement": "무응답"},
    {"plan_year": 2018, "province": "서울", "district": "강서구", "title": "강서어린이 동화축제", "lookup_key": lookup.lookup_key("강서어린이 동화축제"), "prior_attendance": 10000, "measurement": "미제공"},
])


def region(code, name):
    return RegionRef(area_code="1", legal_dong_code=code, display_name=name)


def test_lookup_requires_exact_name_province_and_district():
    found = lookup.lookup_previous_attendance(title="2026 강릉단오제", region=region("51150", "강원특별자치도 강릉시"), table=TABLE)
    assert found["prior_attendance"] == 956000
    assert lookup.lookup_previous_attendance(title="강릉 단오 축제", region=region("51150", "강원특별자치도 강릉시"), table=TABLE) is None
    assert lookup.lookup_previous_attendance(title="강릉단오제", region=region("51130", "강원특별자치도 원주시"), table=TABLE) is None


def test_lookup_uses_legal_code_province_to_split_same_district_names():
    assert lookup.lookup_previous_attendance(title="명태축제", region=region("51820", "고성군"), table=TABLE)["prior_attendance"] == 1000
    assert lookup.lookup_previous_attendance(title="명태축제", region=region("48820", "고성군"), table=TABLE)["prior_attendance"] == 2000


def test_lookup_accepts_province_run_festival_and_filters_stale_results():
    found = lookup.lookup_previous_attendance(title="제30회 서울세계도시문화축제", region=region("11140", "서울특별시 중구"), table=TABLE)
    assert found["prior_attendance"] == 160000 and lookup.lookup_key("2026년 30회 서울세계도시문화축제") == "서울세계도시문화축제"
    stale = dict(title="강서어린이 동화축제", region=region("11500", "서울특별시 강서구"), table=TABLE)
    assert lookup.lookup_previous_attendance(**stale)["plan_year"] == 2018
    assert lookup.lookup_previous_attendance(**stale, min_result_year=2023) is None


def test_prior_attendance_is_attached_as_verified_fact_not_prediction(tmp_path, monkeypatch):
    path = tmp_path / "lookup.csv"
    TABLE.to_csv(path, index=False)
    monkeypatch.setenv("HEUNGMAP_MCST_LOOKUP_PATH", str(path))
    from test_prediction_integration import regional_prediction
    prediction = regional_prediction()
    evidence = []
    result = lookup.attach_prior_attendance(prediction, evidence, "강릉단오제", region("51150", "강원특별자치도 강릉시"))
    item = next(entry for entry in result.evidence if entry.evidence_id == "ev_mcst_prior_attendance")
    assert item.value_type == "verified_fact" and "2025년 실적, 계측" in item.display_value and evidence == [item]
    assert any(source.source_id == "src_mcst_festivals" for source in result.sources)
    assert result.primary_metric.p50 == regional_prediction().primary_metric.p50
    AvailablePrediction.model_validate(result.model_dump())
    assert not {"contact", "manager", "phone"} & set(TABLE.columns)


def test_missing_table_is_silently_skipped(tmp_path, monkeypatch):
    monkeypatch.setenv("HEUNGMAP_MCST_LOOKUP_PATH", str(tmp_path / "missing.csv"))
    assert lookup.prior_attendance_evidence("강릉단오제", region("51150", "강원특별자치도 강릉시")) is None
