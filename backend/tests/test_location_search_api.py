import asyncio
from datetime import datetime

from fastapi.testclient import TestClient

from app import main as main_module
from app.main import app
from app.schemas import AddressSearchItem, Coordinates, SourceRef, Venue, VenueSearchItem
from app.services.kakao_address import KakaoAddressUnavailable
from app.services.tourapi import TourApiClient, TourApiUnavailable


client = TestClient(app)


def source(source_id: str, source_type: str = "tourapi") -> SourceRef:
    return SourceRef(
        source_id=source_id,
        source_type=source_type,
        provider_name="테스트 제공자",
        dataset_name="테스트 데이터",
        retrieved_at=datetime.now().astimezone(),
    )


def test_tourapi_keyword_mapping_keeps_capacity_unknown(monkeypatch) -> None:
    tourapi = TourApiClient(service_key="test-key")

    async def fake_get_items(operation, params):
        assert operation == "searchKeyword2"
        assert params["keyword"] == "문화비축기지"
        assert params["areaCode"] == "1"
        return [{
            "contentid": "123",
            "contenttypeid": "14",
            "title": "문화비축기지",
            "addr1": "서울 마포구",
            "addr2": "증산로 87",
            "mapx": "126.8930",
            "mapy": "37.5714",
        }]

    monkeypatch.setattr(tourapi, "_get_items", fake_get_items)
    items = asyncio.run(tourapi.search_venues(keyword="문화비축기지", area_code="1"))
    assert len(items) == 1
    assert items[0].venue.address == "서울 마포구 증산로 87"
    assert items[0].venue.capacity is None
    assert items[0].category == "문화시설"


def test_venue_search_endpoint(monkeypatch) -> None:
    class FakeTourApi:
        configured = True

        async def search_venues(self, **kwargs):
            assert kwargs["keyword"] == "문화비축기지"
            return [VenueSearchItem(
                venue=Venue(
                    venue_id="venue_tourapi_123",
                    name="문화비축기지",
                    address="서울 마포구 증산로 87",
                    coordinates=Coordinates(latitude=37.5714, longitude=126.8930),
                ),
                category="문화시설",
                content_type_id="14",
                source=source("src_tourapi_123"),
            )]

    monkeypatch.setattr(main_module, "tourapi", FakeTourApi())
    response = client.get("/api/v1/venues/search", params={"keyword": "문화비축기지", "area_code": "1"})
    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["venue"]["name"] == "문화비축기지"
    assert data["items"][0]["venue"]["capacity"] is None
    assert data["meta"]["warnings"]


def test_address_search_endpoint(monkeypatch) -> None:
    class FakeKakaoAddress:
        configured = True

        async def search_addresses(self, **kwargs):
            assert kwargs["query"] == "서울 마포구 증산로 87"
            return [AddressSearchItem(
                address_name="서울 마포구 증산로 87",
                road_address_name="서울 마포구 증산로 87",
                jibun_address_name="서울 마포구 성산동 661",
                building_name="문화비축기지",
                coordinates=Coordinates(latitude=37.5714, longitude=126.8930),
                source=source("src_kakao_address_123", "other_public"),
            )]

    monkeypatch.setattr(main_module, "kakao_address", FakeKakaoAddress())
    response = client.get("/api/v1/addresses/search", params={"query": "서울 마포구 증산로 87"})
    assert response.status_code == 200
    assert response.json()["items"][0]["building_name"] == "문화비축기지"


def test_search_upstream_failures_use_problem_json(monkeypatch) -> None:
    class FailingTourApi:
        configured = False

        async def search_venues(self, **_kwargs):
            raise TourApiUnavailable("TOURAPI_SERVICE_KEY가 설정되지 않았습니다.")

    class FailingKakaoAddress:
        configured = False

        async def search_addresses(self, **_kwargs):
            raise KakaoAddressUnavailable("KAKAO_REST_API_KEY가 설정되지 않았습니다.")

    monkeypatch.setattr(main_module, "tourapi", FailingTourApi())
    monkeypatch.setattr(main_module, "kakao_address", FailingKakaoAddress())

    for path, params in (
        ("/api/v1/venues/search", {"keyword": "문화비축기지"}),
        ("/api/v1/addresses/search", {"query": "서울 마포구"}),
    ):
        response = client.get(path, params=params)
        assert response.status_code == 503
        assert response.headers["content-type"].startswith("application/problem+json")
        assert response.json()["code"] == "UPSTREAM_UNAVAILABLE"


def test_search_query_requires_two_characters() -> None:
    response = client.get("/api/v1/venues/search", params={"keyword": "서"})
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
