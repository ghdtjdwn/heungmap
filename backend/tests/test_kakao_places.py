import asyncio

import httpx

from app.schemas import Coordinates
from app.services.kakao_places import KakaoPlacesClient


def test_kakao_category_search_maps_parking_and_lodging_and_uses_cache() -> None:
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "KakaoAK test-key"
        params = dict(request.url.params)
        category = params["category_group_code"]
        calls.append(category)
        assert params["x"] == "126.9"
        assert params["y"] == "37.5"
        assert params["radius"] == "3000"
        assert params["sort"] == "distance"
        document = {
            "id": "parking-1" if category == "PK6" else "lodging-1",
            "place_name": "테스트 주차장" if category == "PK6" else "테스트 호텔",
            "road_address_name": "서울 마포구 테스트로 1",
            "address_name": "서울 마포구 테스트동 1",
            "x": "126.901",
            "y": "37.501",
            "distance": "240" if category == "PK6" else "510",
            "place_url": f"https://place.map.kakao.com/{category.lower()}",
        }
        return httpx.Response(200, json={"meta": {"is_end": True}, "documents": [document]})

    original = httpx.AsyncClient

    class MockClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            super().__init__(*args, **kwargs)

    httpx.AsyncClient = MockClient
    try:
        client = KakaoPlacesClient(rest_api_key="test-key", cache_ttl_seconds=60)
        coordinates = Coordinates(latitude=37.5, longitude=126.9)
        first = asyncio.run(client.nearby_places(coordinates, 3000))
        second = asyncio.run(client.nearby_places(coordinates, 3000))
    finally:
        httpx.AsyncClient = original

    assert calls == ["PK6", "AD5"]
    assert {place.place_type for place in first} == {"parking", "lodging"}
    assert first[0].distance_m == 240
    assert str(first[0].sources[0].source_url).startswith("https://place.map.kakao.com/")
    assert second == first
    assert client.diagnostics["cache_hits"] == 1
