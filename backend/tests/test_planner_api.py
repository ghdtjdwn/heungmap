from copy import deepcopy

from fastapi.testclient import TestClient

from app import main as main_module
from app.main import analysis_cache, app
from app.services.tourapi import TourApiUnavailable


client = TestClient(app)


def valid_request() -> dict:
    return {
        "contract_version": "0.1.0",
        "client_request_id": "f090c1e8-6ef1-4d06-a31e-561cad950644",
        "event_draft": {
            "event_id": "evt_planner_test_001",
            "working_title": "가상 청년 음악축제",
            "planner_type": "independent_planner",
            "planning_stage": "idea",
            "event_type": "festival",
            "purpose": "community",
            "theme_keywords": ["청년", "음악"],
            "schedule_selection_mode": "fixed",
            "start_date": "2026-10-10",
            "end_date": "2026-10-10",
            "region_selection_mode": "fixed",
            "region": {"area_code": "1", "display_name": "서울"},
            "indoor_outdoor": "outdoor",
            "target_audience": ["young_adult", "local_resident"],
            "target_attendance": 500,
            "ticket_type": "free",
            "budget_max_krw": 10000000,
            "fixed_constraints": ["개최일 변경 불가"],
        },
        "requested_outputs": ["prediction", "nearby_places", "rule_recommendations"],
    }


def setup_function() -> None:
    analysis_cache.clear()


def test_health() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["contract_version"] == "0.1.0"


def test_analysis_returns_labeled_mock_and_rules() -> None:
    response = client.post("/api/v1/planner/analyses", json=valid_request())
    assert response.status_code == 200
    data = response.json()
    assert data["prediction"]["status"] == "available"
    assert data["prediction"]["prediction_type"] == "relative_demand_score"
    assert data["prediction"]["is_mock"] is True
    assert data["prediction"]["method"] == "rules"
    assert data["nearby_places"]["reason_code"] == "missing_coordinates"
    assert any(item["category"] == "risk" for item in data["rule_recommendations"])


def test_invalid_date_order_uses_problem_json() -> None:
    payload = valid_request()
    payload["event_draft"]["end_date"] = "2026-10-01"
    response = client.post("/api/v1/planner/analyses", json=payload)
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_fixed_schedule_requires_dates() -> None:
    payload = valid_request()
    payload["event_draft"].pop("start_date")
    response = client.post("/api/v1/planner/analyses", json=payload)
    assert response.status_code == 422
    assert response.json()["field_errors"]


def test_same_id_and_body_returns_same_analysis() -> None:
    payload = valid_request()
    first = client.post("/api/v1/planner/analyses", json=payload)
    second = client.post("/api/v1/planner/analyses", json=payload)
    assert first.status_code == second.status_code == 200
    assert first.json()["analysis_id"] == second.json()["analysis_id"]


def test_same_id_and_different_body_returns_conflict() -> None:
    first_payload = valid_request()
    second_payload = deepcopy(first_payload)
    second_payload["event_draft"]["working_title"] = "다른 기획"
    assert client.post("/api/v1/planner/analyses", json=first_payload).status_code == 200
    response = client.post("/api/v1/planner/analyses", json=second_payload)
    assert response.status_code == 409
    assert response.json()["code"] == "IDEMPOTENCY_CONFLICT"


def test_large_event_adds_operation_recommendation() -> None:
    payload = valid_request()
    payload["client_request_id"] = "49778df4-e8c6-4256-ac86-206482e4874e"
    payload["event_draft"]["target_attendance"] = 20000
    response = client.post("/api/v1/planner/analyses", json=payload)
    assert response.status_code == 200
    assert any(item["category"] == "operation" and item["priority"] == "high" for item in response.json()["rule_recommendations"])


def test_small_and_large_scenarios_return_different_priorities() -> None:
    small = valid_request()
    large = deepcopy(small)
    large["client_request_id"] = "076b36ba-bb0f-4ef5-b5bd-3241358ff754"
    large["event_draft"]["target_attendance"] = 20000
    small_items = client.post("/api/v1/planner/analyses", json=small).json()["rule_recommendations"]
    large_items = client.post("/api/v1/planner/analyses", json=large).json()["rule_recommendations"]
    assert not any(item["category"] == "operation" and item["priority"] == "high" for item in small_items)
    assert any(item["category"] == "operation" and item["priority"] == "high" for item in large_items)


def test_unknown_schedule_and_region_still_complete() -> None:
    payload = valid_request()
    payload["client_request_id"] = "7c18d106-60cb-42fb-91a7-e8d8c1d16e43"
    payload["event_draft"]["schedule_selection_mode"] = "unknown"
    payload["event_draft"].pop("start_date")
    payload["event_draft"].pop("end_date")
    payload["event_draft"]["region_selection_mode"] = "unknown"
    payload["event_draft"].pop("region")
    response = client.post("/api/v1/planner/analyses", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["prediction"]["status"] == "available"
    assert any(item["category"] == "tourism" for item in data["rule_recommendations"])


def test_tourapi_failure_preserves_mock_and_rules(monkeypatch) -> None:
    class FailingTourApi:
        configured = True

        async def competing_festival_count(self, **_kwargs):
            raise TourApiUnavailable("fixture failure")

        async def nearby_places(self, _coordinates):
            raise TourApiUnavailable("fixture failure")

    payload = valid_request()
    payload["client_request_id"] = "4baad938-57ea-40cb-b55e-c51de35d2b6e"
    payload["event_draft"]["venue"] = {
        "name": "가상 장소",
        "coordinates": {"latitude": 37.5665, "longitude": 126.9780},
    }
    monkeypatch.setattr(main_module, "tourapi", FailingTourApi())
    response = client.post("/api/v1/planner/analyses", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["prediction"]["status"] == "available"
    assert data["nearby_places"]["status"] == "unavailable"
    assert data["nearby_places"]["retryable"] is True
    assert data["rule_recommendations"]
    assert data["meta"]["warnings"]
