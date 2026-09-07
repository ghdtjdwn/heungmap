import asyncio
import json
import time

import httpx

from app.services.cache import TtlCache
from app.services.kakao_address import KakaoAddressClient
from app.services.tourapi import TourApiClient


def test_ttl_cache_expires_and_evicts_lru() -> None:
    cache: TtlCache[int] = TtlCache(ttl_seconds=0.02, max_entries=2)
    cache.set("a", 1)
    cache.set("b", 2)
    assert cache.get("a") == 1
    cache.set("c", 3)
    assert cache.get("b") is None
    time.sleep(0.03)
    assert cache.get("a") is None


def test_tourapi_identical_search_uses_cache() -> None:
    calls = 0

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"response": {"header": {"resultCode": "0000"}, "body": {"totalCount": 0, "items": ""}}})

    tourapi = TourApiClient(service_key="test", cache_ttl_seconds=60)
    original = httpx.AsyncClient

    class MockClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            super().__init__(*args, **kwargs)

    httpx.AsyncClient = MockClient
    try:
        asyncio.run(tourapi.search_venues(keyword="테스트"))
        asyncio.run(tourapi.search_venues(keyword="테스트"))
    finally:
        httpx.AsyncClient = original
    assert calls == 1
    assert tourapi.diagnostics["cache_hits"] == 1
