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
from app.services.tourapi import TourApiClient, TourApiUnavailable


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


def test_event_list_returns_items_sorted_by_start_date(monkeypatch) -> None:
    class FakeTourApi:
        configured = True

        async def search_festivals(self, **kwargs):
            assert kwargs["area_code"] == "1"
            later = event()
            earlier = later.model_copy(update={"event_id": "evt_tourapi_456", "start_date": date.today() + timedelta(days=3)})
            return [later, earlier]

    monkeypatch.setattr(main_module, "tourapi", FakeTourApi())
    response = client.get("/api/v1/events", params={"area_code": "1", "sort": "start_date"})
    assert response.status_code == 200
    data = response.json()
    assert [item["event_id"] for item in data["items"]] == ["evt_tourapi_456", "evt_tourapi_123"]
    assert data["applied_filters"]["sort"] == "start_date"
    assert data["total_count"] == 2


def test_event_list_rejects_unsupported_sort_location_and_reversed_dates() -> None:
    unsupported_sort = client.get("/api/v1/events", params={"sort": "demand"})
    assert unsupported_sort.status_code == 422
    assert unsupported_sort.json()["code"] == "VALIDATION_ERROR"

    unsupported_location = client.get(
        "/api/v1/events",
        params={"latitude": 37.5, "longitude": 127.0},
    )
    assert unsupported_location.status_code == 422
    assert {error["field"] for error in unsupported_location.json()["field_errors"]} == {
        "latitude",
        "longitude",
    }

    reversed_dates = client.get(
        "/api/v1/events",
        params={"start_date": "2026-10-02", "end_date": "2026-10-01"},
    )
    assert reversed_dates.status_code == 422
    assert reversed_dates.json()["field_errors"] == [
        {"field": "start_date", "message": "종료일보다 늦을 수 없습니다."}
    ]


def test_event_list_filters_and_sorts_before_pagination(monkeypatch) -> None:
    tourapi = TourApiClient(service_key="test-key")
    late_date = (date.today() + timedelta(days=20)).strftime("%Y%m%d")
    early_date = (date.today() + timedelta(days=2)).strftime("%Y%m%d")

    def raw_event(content_id: str, title: str, start: str) -> dict[str, str]:
        return {
            "contentid": content_id,
            "title": title,
            "eventstartdate": start,
            "eventenddate": start,
            "areacode": "1",
            "sigungucode": "2",
            "addr1": "서울 마포구",
        }

    first_upstream_page = [raw_event(str(index), f"일반 축제 {index}", late_date) for index in range(100)]
    second_upstream_page = [raw_event("999", "찾을 축제", early_date)]

    async def fake_get_items(operation, params):
        assert operation == "searchFestival2"
        return first_upstream_page if params["pageNo"] == 1 else second_upstream_page

    monkeypatch.setattr(tourapi, "_get_items", fake_get_items)
    monkeypatch.setattr(main_module, "tourapi", tourapi)

    searched = client.get("/api/v1/events", params={"query": "찾을", "page": 1, "page_size": 2})
    assert searched.status_code == 200
    assert [item["event_id"] for item in searched.json()["items"]] == ["evt_tourapi_999"]
    assert searched.json()["total_count"] == 1

    sorted_page = client.get("/api/v1/events", params={"sort": "start_date", "page": 1, "page_size": 1})
    assert sorted_page.status_code == 200
    assert sorted_page.json()["items"][0]["event_id"] == "evt_tourapi_999"
    assert sorted_page.json()["total_count"] == 101


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


def test_nearby_omits_missing_distance(monkeypatch) -> None:
    class FakeTourApi:
        configured = True

        async def get_festival_by_id(self, _content_id):
            return event(detail=True)

        async def nearby_places(self, _coordinates, _radius_m):
            return [
                NearbyPlace(
                    place_id="place_tourapi_without_distance",
                    place_type="tourist_attraction",
                    name="거리 미제공 관광지",
                    sources=[source("src_tourapi_place_without_distance")],
                )
            ]

    monkeypatch.setattr(main_module, "tourapi", FakeTourApi())
    response = client.get("/api/v1/events/evt_tourapi_123/nearby")
    assert response.status_code == 200
    assert "distance_m" not in response.json()["items"][0]


def test_detail_intro_timeout_is_not_reported_as_missing_event(monkeypatch) -> None:
    tourapi = TourApiClient(service_key="test-key")

    async def fake_get_items(operation, _params):
        if operation == "detailCommon2":
            return [{"contentid": "123", "title": "테스트 축제", "addr1": "서울 마포구"}]
        if operation == "detailIntro2":
            raise TourApiUnavailable("TourAPI 응답 시간이 초과됐습니다.", reason="timeout")
        raise AssertionError(f"unexpected operation: {operation}")

    monkeypatch.setattr(tourapi, "_get_items", fake_get_items)
    monkeypatch.setattr(main_module, "tourapi", tourapi)

    detail = client.get("/api/v1/events/evt_tourapi_123")
    assert detail.status_code == 504
    assert detail.json()["code"] == "UPSTREAM_TIMEOUT"
    nearby = client.get("/api/v1/events/evt_tourapi_123/nearby")
    assert nearby.status_code == 504
    assert nearby.json()["code"] == "UPSTREAM_TIMEOUT"
    prediction = client.get("/api/v1/events/evt_tourapi_123/prediction")
    assert prediction.status_code == 200
    assert prediction.json()["status"] == "unavailable"
    assert prediction.json()["reason_code"] == "upstream_unavailable"
    assert prediction.json()["retryable"] is True


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
