from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import main as main_module
from app.main import app
from app.schemas import AvailablePrediction, PredictionRangeMetric, RegionRef
from app.services.tourapi import TourApiClient
from test_events_api import event
from test_planner_api import valid_request


def regional_prediction(event_id="evt_planner_test_001"):
    now = datetime.now().astimezone()
    return AvailablePrediction(
        status="available", prediction_id="pred_regional_test", event_id=event_id,
        prediction_type="regional_visit_demand", as_of=now,
        target_start_date=date.today() + timedelta(days=7), target_end_date=date.today() + timedelta(days=8),
        target_region=RegionRef(area_code="1", legal_dong_code="11440", display_name="서울 마포구"),
        primary_metric=PredictionRangeMetric(metric_name="regional_visit_demand", unit="percent_change", p10=-20, p50=-5, p90=10),
        components=[dict(component_type="regional_baseline", value=100, unit="index_points",
                         scope_description="행사 직전 28일 지역 방문자 중앙값을 100으로 정의한 기준입니다.", evidence_refs=["ev_baseline"])],
        confidence="low", data_sufficiency="limited", method="machine_learning", model_version="regional-test-v1",
        factors=[], evidence=[dict(evidence_id="ev_baseline", value_type="derived_value", label="지역 기준", display_value="기준 지수 100", source_refs=["src_datalab"])],
        sources=[dict(source_id="src_datalab", source_type="kto_datalab", provider_name="한국관광공사", dataset_name="지역별 방문자수", retrieved_at=now),
                 dict(source_id="src_model", source_type="heungmap_model", provider_name="흥할지도", dataset_name="지역 방문수요 모델", retrieved_at=now)],
        limitations=["지역 전체 방문수요이며 특정 행사 관람객 수가 아닙니다."],
        out_of_distribution=False, fallback_used=False, is_mock=False, created_at=now,
    )


def test_percent_change_range_allows_decline_but_rejects_invalid_values():
    assert regional_prediction().primary_metric.p50 == -5
    for values in [(-101, -5, 10), (0, -5, 10), (-20, float("nan"), 10), (-20, -5, float("inf"))]:
        with pytest.raises(ValidationError):
            PredictionRangeMetric(metric_name="regional_visit_demand", unit="percent_change", p10=values[0], p50=values[1], p90=values[2])
    with pytest.raises(ValidationError):
        PredictionRangeMetric(metric_name="regional_visit_demand", unit="people", p10=-1, p50=5, p90=10)
    payload = regional_prediction().model_dump()
    for field in ("target_region", "components"):
        with pytest.raises(ValidationError):
            AvailablePrediction.model_validate({**payload, field: None})


@pytest.mark.parametrize("codes", [
    {"lDongRegnCd": "11", "lDongSignguCd": "440"},
    {"ldongregncd": "11", "ldongsigngucd": "440"},
    {"lDongRegnCd": "11440"},
    {"lDongSignguCd": "11440"},
])
def test_tourapi_preserves_legal_sigungu_code(codes):
    summary = TourApiClient()._festival_to_summary(
        dict(contentid="123", title="가상 축제", eventstartdate="20260920", eventenddate="20260921",
             areacode="1", sigungucode="14", **codes), datetime.now().astimezone())
    assert summary.region.legal_dong_code == "11440"


def test_real_regional_prediction_reaches_planner_publication_and_visitor(monkeypatch):
    from app.demand import daily_service as service

    monkeypatch.setenv("HEUNGMAP_DEMAND_MODE", "auto")
    monkeypatch.setattr(main_module, "tourapi", type("OfflineTourApi", (), {"configured": False})())
    calls = []
    def predict(**kwargs):
        calls.append(kwargs)
        return regional_prediction(kwargs["event_id"])
    monkeypatch.setattr(service, "predict_demand", predict)
    headers = {"Origin": "http://localhost:3000"}
    with TestClient(app) as client:
        client.post("/api/v1/auth/mock", headers=headers)
        client.post("/api/v1/auth/role", json={"role": "planner"}, headers=headers)
        request = valid_request()
        request["client_request_id"] = str(uuid4())
        request["event_draft"]["region"] = regional_prediction().target_region.model_dump(exclude_none=True)
        request["event_draft"]["venue"] = {"name": "확정 장소"}
        response = client.post("/api/v1/planner/analyses", json=request, headers=headers)
        assert response.status_code == 200
        analysis = response.json()
        assert analysis["prediction"]["is_mock"] is False
        assert analysis["prediction"]["primary_metric"]["p50"] == -5
        assert "ev_baseline" in {item["evidence_id"] for item in analysis["evidence"]}
        assert calls[0]["region"].legal_dong_code == "11440"
        published = client.post("/api/v1/planner/publications", json={"analysis_id": analysis["analysis_id"], "description": "공개 소개", "consent": True}, headers=headers)
        assert published.status_code == 200
        prediction = client.get("/api/v1/events/evt_planner_test_001/prediction").json()
        assert prediction["prediction_id"] == analysis["prediction"]["prediction_id"]
        assert prediction["primary_metric"] == analysis["prediction"]["primary_metric"]
        assert prediction["components"][0]["evidence_refs"] == []
        assert prediction["evidence"] == []
        assert "src_datalab" in {source["source_id"] for source in prediction["sources"]}
        assert "10000000" not in str(prediction)


def test_visitor_and_region_catalog_use_shared_model_service(monkeypatch):
    from app.demand import daily_service as service

    monkeypatch.setenv("HEUNGMAP_DEMAND_MODE", "auto")
    monkeypatch.setattr(service, "predict_demand", lambda **kwargs: regional_prediction(kwargs["event_id"]))
    monkeypatch.setattr(service, "prediction_regions", lambda: [regional_prediction().target_region])
    class TourApi:
        async def get_festival_by_id(self, content_id):
            return event(detail=True)
    monkeypatch.setattr(main_module, "tourapi", TourApi())
    with TestClient(app) as client:
        prediction = client.get("/api/v1/events/evt_tourapi_123/prediction").json()
        assert prediction["primary_metric"]["unit"] == "percent_change"
        assert prediction["event_id"] == "evt_tourapi_123"
        assert client.get("/api/v1/prediction/regions").json()[0]["legal_dong_code"] == "11440"


def test_unknown_planner_schedule_returns_unavailable_without_model(monkeypatch):
    monkeypatch.setenv("HEUNGMAP_DEMAND_MODE", "auto")
    headers = {"Origin": "http://localhost:3000"}
    with TestClient(app) as client:
        client.post("/api/v1/auth/mock", headers=headers)
        request = valid_request()
        request["client_request_id"] = str(uuid4())
        request["event_draft"].update(schedule_selection_mode="unknown", start_date=None, end_date=None)
        response = client.post("/api/v1/planner/analyses", json=request, headers=headers)
        assert response.status_code == 200
        assert response.json()["prediction"]["reason_code"] == "missing_required_input"
        assert response.json()["prediction"]["is_mock"] is False
