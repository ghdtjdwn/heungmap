from datetime import date, datetime, timedelta

from fastapi.testclient import TestClient

from app import main as main_module
from app.main import app
from app.schemas import (
    Coordinates,
    DataQuality,
    EventDetail,
    EventSummary,
    NearbyPlace,
    RegionRef,
    SourceRef,
    Venue,
)
from app.services.tourapi import TourApiUnavailable


client = TestClient(app)


def source(source_id: str = "src_tourapi_test") -> SourceRef:
    return SourceRef(
        source_id=source_id,
        source_type="tourapi",
        provider_name="한국관광공사",
        dataset_name="테스트 TourAPI",
        retrieved_at=datetime.now().astimezone(),
    )


def event(*, detail: bool = False, coordinates: bool = True):
    fields = dict(
        event_id="evt_tourapi_123",
        origin="tourapi",
        visibility="public",
        title="테스트 축제",
        event_type="festival",
        event_status="scheduled",
        start_date=date.today() + timedelta(days=7),
        end_date=date.today() + timedelta(days=8),
        region=RegionRef(area_code="1", sigungu_code="2", display_name="서울 마포구"),
        venue=Venue(
            name="테스트 광장",
            address="서울 마포구",
            coordinates=Coordinates(latitude=37.5, longitude=126.9) if coordinates else None,
        ),
        sources=[source()],
        data_quality=DataQuality(completeness="high", warnings=[], is_mock=False),
        updated_at=datetime.now().astimezone(),
    )
    return EventDetail(**fields, description="축제 설명") if detail else EventSummary(**fields)


def test_event_list_returns_sorted_tourapi_items(monkeypatch) -> None:
    class FakeTourApi:
        configured = True

        async def search_festivals(self, **kwargs):
            assert kwargs["area_code"] == "1"
            later = event()
            earlier = later.model_copy(update={"event_id": "evt_tourapi_456", "start_date": date.today() + timedelta(days=3)})
            return [later, earlier]

    monkeypatch.setattr(main_module, "tourapi", FakeTourApi())
    response = client.get("/api/v1/events", params={"area_code": "1", "sort": "demand"})
    assert response.status_code == 200
    data = response.json()
    assert [item["event_id"] for item in data["items"]] == ["evt_tourapi_456", "evt_tourapi_123"]
    assert data["applied_filters"]["sort"] == "demand"
    assert "total_count" not in data


def test_missing_event_returns_problem_json(monkeypatch) -> None:
    class FakeTourApi:
        configured = True

        async def get_festival_by_id(self, _content_id):
            return None

    monkeypatch.setattr(main_module, "tourapi", FakeTourApi())
    response = client.get("/api/v1/events/evt_tourapi_doesnotexist")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "EVENT_NOT_FOUND"


def test_event_list_upstream_failure_returns_503(monkeypatch) -> None:
    class FakeTourApi:
        configured = False

        async def search_festivals(self, **_kwargs):
            raise TourApiUnavailable("TOURAPI_SERVICE_KEY가 설정되지 않았습니다.", reason="not_configured")

    monkeypatch.setattr(main_module, "tourapi", FakeTourApi())
    response = client.get("/api/v1/events")
    assert response.status_code == 503
    assert response.json()["code"] == "UPSTREAM_NOT_CONFIGURED"


def test_nearby_requires_coordinates_and_returns_places(monkeypatch) -> None:
    class FakeTourApi:
        configured = True
        with_coordinates = False

        async def get_festival_by_id(self, _content_id):
            return event(detail=True, coordinates=self.with_coordinates)

        async def nearby_places(self, coordinates, radius_m):
            assert coordinates.latitude == 37.5
            assert radius_m == 3000
            return [
                NearbyPlace(
                    place_id="place_tourapi_9",
                    place_type="tourist_attraction",
                    name="주변 관광지",
                    distance_m=250,
                    sources=[source("src_tourapi_place_9")],
                )
            ]

    fake = FakeTourApi()
    monkeypatch.setattr(main_module, "tourapi", fake)
    missing = client.get("/api/v1/events/evt_tourapi_123/nearby")
    assert missing.status_code == 422
    assert missing.json()["code"] == "VALIDATION_ERROR"

    fake.with_coordinates = True
    response = client.get("/api/v1/events/evt_tourapi_123/nearby")
    assert response.status_code == 200
    assert response.json()["items"][0]["name"] == "주변 관광지"


def test_event_prediction_is_low_confidence_mock(monkeypatch) -> None:
    class FakeTourApi:
        configured = True

        async def get_festival_by_id(self, _content_id):
            return event(detail=True)

        async def competing_festival_count(self, **_kwargs):
            return 2, source("src_tourapi_competition")

    monkeypatch.setattr(main_module, "tourapi", FakeTourApi())
    response = client.get("/api/v1/events/evt_tourapi_123/prediction")
    assert response.status_code == 200
    data = response.json()
    assert data["is_mock"] is True
    assert data["confidence"] == "low"
    assert data["prediction_type"] == "relative_demand_score"
