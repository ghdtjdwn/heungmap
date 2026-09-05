from __future__ import annotations

import os
import re
import json
from datetime import date, datetime
from html import unescape
from typing import Any

import httpx

from app.schemas import Coordinates, NearbyPlace, RegionRef, SourceRef, Venue, VenueSearchItem
from app.services.cache import TtlCache


BASE_URL = "https://apis.data.go.kr/B551011/KorService2"


class TourApiUnavailable(RuntimeError):
    def __init__(self, message: str, *, reason: str = "upstream") -> None:
        super().__init__(message)
        self.reason = reason


class TourApiClient:
    def __init__(self, service_key: str | None = None, timeout_seconds: float = 6.0, *, cache_ttl_seconds: float = 300, cache_max_entries: int = 256) -> None:
        self.service_key = (service_key or os.getenv("TOURAPI_SERVICE_KEY", "")).strip()
        self.timeout_seconds = timeout_seconds
        self.cache: TtlCache[list[dict[str, Any]]] = TtlCache(ttl_seconds=cache_ttl_seconds, max_entries=cache_max_entries)
        self.upstream_calls = 0

    @property
    def configured(self) -> bool:
        return bool(self.service_key)

    def _params(self) -> dict[str, str]:
        if not self.service_key:
            raise TourApiUnavailable("TOURAPI_SERVICE_KEY가 설정되지 않았습니다.", reason="not_configured")
        return {
            "serviceKey": self.service_key,
            "MobileOS": "ETC",
            "MobileApp": "HeungMap",
            "_type": "json",
        }

    async def _get_items(self, operation: str, params: dict[str, str | int | float]) -> list[dict[str, Any]]:
        cache_key = json.dumps([operation, sorted(params.items())], ensure_ascii=False, separators=(",", ":"))
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        query: dict[str, str | int | float] = {**self._params(), **params}
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                self.upstream_calls += 1
                response = await client.get(f"{BASE_URL}/{operation}", params=query)
                if response.status_code == 429:
                    raise TourApiUnavailable("TourAPI 호출 한도에 도달했습니다.", reason="quota")
                if response.status_code in {401, 403}:
                    raise TourApiUnavailable("TourAPI 활용 권한을 확인해 주세요.", reason="permission")
                if response.status_code >= 500:
                    raise TourApiUnavailable("TourAPI가 일시적인 서버 오류를 반환했습니다.", reason="upstream")
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException as exc:
            raise TourApiUnavailable("TourAPI 응답 시간이 초과됐습니다.", reason="timeout") from exc
        except TourApiUnavailable:
            raise
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise TourApiUnavailable("한국관광공사 TourAPI를 불러오지 못했습니다.", reason="upstream") from exc

        try:
            header = payload["response"]["header"]
            result_code = str(header.get("resultCode", ""))
            if result_code not in {"0", "00", "0000"}:
                reason = "quota" if result_code in {"22", "23"} else "permission" if result_code in {"20", "30", "31"} else "upstream"
                raise TourApiUnavailable("한국관광공사 TourAPI가 오류를 반환했습니다.", reason=reason)
            raw_items = payload["response"]["body"].get("items") or {}
            items = raw_items.get("item") or []
        except (KeyError, AttributeError, TypeError) as exc:
            raise TourApiUnavailable("한국관광공사 TourAPI 응답 형식을 해석하지 못했습니다.") from exc
        if isinstance(items, dict):
            result = [items]
            self.cache.set(cache_key, result)
            return result
        if not isinstance(items, list):
            raise TourApiUnavailable("한국관광공사 TourAPI 행사 목록 형식이 올바르지 않습니다.")
        result = [item for item in items if isinstance(item, dict)]
        self.cache.set(cache_key, result)
        return result

    @property
    def diagnostics(self) -> dict[str, int]:
        stats = self.cache.stats
        return {"upstream_calls": self.upstream_calls, "cache_hits": stats.hits, "cache_misses": stats.misses, "cache_entries": stats.entries}

    @staticmethod
    def _text(value: Any) -> str:
        return re.sub(r"<[^>]+>", "", unescape(str(value or ""))).strip()

    async def search_venues(
        self,
        *,
        keyword: str,
        area_code: str | None = None,
        limit: int = 10,
    ) -> list[VenueSearchItem]:
        params: dict[str, str | int] = {
            "keyword": keyword,
            "arrange": "A",
            "pageNo": 1,
            "numOfRows": limit,
        }
        if area_code:
            params["areaCode"] = area_code
        items = await self._get_items("searchKeyword2", params)
        now = datetime.now().astimezone()
        categories = {
            "12": "관광지",
            "14": "문화시설",
            "15": "축제·행사",
            "25": "여행코스",
            "28": "레포츠",
            "32": "숙박",
            "38": "쇼핑",
            "39": "음식점",
        }
        results: list[VenueSearchItem] = []
        for item in items:
            content_id = self._text(item.get("contentid"))
            title = self._text(item.get("title"))
            if not content_id or not title:
                continue
            coordinates = None
            try:
                if item.get("mapx") not in (None, "") and item.get("mapy") not in (None, ""):
                    coordinates = Coordinates(latitude=float(item["mapy"]), longitude=float(item["mapx"]))
            except (TypeError, ValueError):
                coordinates = None
            address = " ".join(
                part for part in (self._text(item.get("addr1")), self._text(item.get("addr2"))) if part
            ) or None
            content_type_id = self._text(item.get("contenttypeid")) or None
            source = SourceRef(
                source_id=f"src_tourapi_keyword_{content_id}",
                source_type="tourapi",
                provider_name="한국관광공사",
                dataset_name="국문 관광정보 서비스 searchKeyword2",
                source_record_id=content_id,
                retrieved_at=now,
                limitation="관광 콘텐츠 검색 결과이며 대관 가능 여부·공식 수용인원·시설 현황은 장소 운영자에게 별도 확인해야 합니다.",
            )
            results.append(
                VenueSearchItem(
                    venue=Venue(
                        venue_id=f"venue_tourapi_{content_id}",
                        name=title,
                        address=address,
                        coordinates=coordinates,
                    ),
                    category=categories.get(content_type_id or "", "기타 관광정보"),
                    content_type_id=content_type_id,
                    source=source,
                )
            )
        return results[:limit]

    async def competing_festival_count(
        self,
        *,
        region: RegionRef,
        start_date: date,
        end_date: date,
    ) -> tuple[int, SourceRef]:
        items = await self._get_items(
            "searchFestival2",
            {
                "eventStartDate": start_date.strftime("%Y%m%d"),
                "eventEndDate": end_date.strftime("%Y%m%d"),
                "areaCode": region.area_code,
                "sigunguCode": region.sigungu_code or "",
                "arrange": "A",
                "pageNo": 1,
                "numOfRows": 100,
            },
        )
        now = datetime.now().astimezone()
        source = SourceRef(
            source_id=f"src_tourapi_festivals_{now.strftime('%Y%m%d%H%M%S')}",
            source_type="tourapi",
            provider_name="한국관광공사",
            dataset_name="국문 관광정보 서비스 searchFestival2",
            retrieved_at=now,
            limitation="같은 지역·기간의 TourAPI 행사 수이며 경쟁 강도나 관람객 수를 뜻하지 않습니다.",
        )
        return len(items), source

    async def nearby_places(self, coordinates: Coordinates, radius_m: int = 5000) -> list[NearbyPlace]:
        items = await self._get_items(
            "locationBasedList2",
            {
                "mapX": coordinates.longitude,
                "mapY": coordinates.latitude,
                "radius": radius_m,
                "arrange": "E",
                "pageNo": 1,
                "numOfRows": 12,
            },
        )
        now = datetime.now().astimezone()
        places: list[NearbyPlace] = []
        for item in items:
            content_id = str(item.get("contentid", "")).strip()
            title = str(item.get("title", "")).strip()
            if not content_id or not title:
                continue
            source = SourceRef(
                source_id=f"src_tourapi_place_{content_id}",
                source_type="tourapi",
                provider_name="한국관광공사",
                dataset_name="국문 관광정보 서비스 locationBasedList2",
                source_record_id=content_id,
                retrieved_at=now,
            )
            content_type = str(item.get("contenttypeid", ""))
            place_type = {
                "12": "tourist_attraction",
                "14": "cultural_facility",
                "32": "lodging",
                "38": "shopping",
                "39": "restaurant",
            }.get(content_type, "other")
            point = None
            try:
                if item.get("mapy") and item.get("mapx"):
                    point = Coordinates(latitude=float(item["mapy"]), longitude=float(item["mapx"]))
            except (TypeError, ValueError):
                point = None
            try:
                distance = int(float(item["dist"])) if item.get("dist") not in (None, "") else None
            except (TypeError, ValueError):
                distance = None
            places.append(
                NearbyPlace(
                    place_id=f"place_tourapi_{content_id}",
                    place_type=place_type,
                    name=title,
                    address=str(item.get("addr1", "")).strip() or None,
                    coordinates=point,
                    distance_m=distance,
                    sources=[source],
                )
            )
        return places
