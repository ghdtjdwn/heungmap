from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

import httpx

from app.schemas import Coordinates, NearbyPlace, SourceRef
from app.services.cache import TtlCache


BASE_URL = "https://dapi.kakao.com/v2/local/search/category.json"
CATEGORIES = (("PK6", "parking"), ("AD5", "lodging"))


class KakaoPlacesUnavailable(RuntimeError):
    def __init__(self, message: str, *, reason: str = "upstream") -> None:
        super().__init__(message)
        self.reason = reason


class KakaoPlacesClient:
    def __init__(
        self,
        rest_api_key: str | None = None,
        timeout_seconds: float = 6.0,
        *,
        cache_ttl_seconds: float = 300,
        cache_max_entries: int = 256,
    ) -> None:
        self.rest_api_key = (rest_api_key or os.getenv("KAKAO_REST_API_KEY", "")).strip()
        self.timeout_seconds = timeout_seconds
        self.cache: TtlCache[list[NearbyPlace]] = TtlCache(
            ttl_seconds=cache_ttl_seconds,
            max_entries=cache_max_entries,
        )
        self.upstream_calls = 0

    @property
    def configured(self) -> bool:
        return bool(self.rest_api_key)

    async def nearby_places(
        self,
        coordinates: Coordinates,
        radius_m: int,
        *,
        per_category: int = 6,
    ) -> list[NearbyPlace]:
        if not self.rest_api_key:
            raise KakaoPlacesUnavailable(
                "KAKAO_REST_API_KEY가 설정되지 않았습니다.",
                reason="not_configured",
            )
        if not 1 <= per_category <= 15:
            raise ValueError("per_category는 1~15여야 합니다.")

        cache_key = json.dumps(
            [coordinates.latitude, coordinates.longitude, radius_m, per_category],
            separators=(",", ":"),
        )
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        documents_by_category: list[tuple[str, str, list[dict[str, Any]]]] = []
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                for category_code, place_type in CATEGORIES:
                    self.upstream_calls += 1
                    response = await client.get(
                        BASE_URL,
                        params={
                            "category_group_code": category_code,
                            "x": coordinates.longitude,
                            "y": coordinates.latitude,
                            "radius": radius_m,
                            "sort": "distance",
                            "page": 1,
                            "size": per_category,
                        },
                        headers={"Authorization": f"KakaoAK {self.rest_api_key}"},
                    )
                    if response.status_code == 429:
                        raise KakaoPlacesUnavailable(
                            "Kakao Local 호출 한도에 도달했습니다.",
                            reason="quota",
                        )
                    if response.status_code in {401, 403}:
                        raise KakaoPlacesUnavailable(
                            "Kakao Local 앱 권한을 확인해 주세요.",
                            reason="permission",
                        )
                    if response.status_code >= 500:
                        raise KakaoPlacesUnavailable(
                            "Kakao Local이 일시적인 서버 오류를 반환했습니다.",
                            reason="upstream",
                        )
                    response.raise_for_status()
                    payload = response.json()
                    documents = payload.get("documents") if isinstance(payload, dict) else None
                    if not isinstance(documents, list):
                        raise KakaoPlacesUnavailable(
                            "Kakao Local 장소 응답 형식을 해석하지 못했습니다."
                        )
                    documents_by_category.append((category_code, place_type, documents))
        except httpx.TimeoutException as exc:
            raise KakaoPlacesUnavailable(
                "Kakao Local 응답 시간이 초과됐습니다.",
                reason="timeout",
            ) from exc
        except KakaoPlacesUnavailable:
            raise
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise KakaoPlacesUnavailable(
                "Kakao Local 주변 장소를 불러오지 못했습니다.",
                reason="upstream",
            ) from exc

        now = datetime.now().astimezone()
        places: list[NearbyPlace] = []
        for category_code, place_type, documents in documents_by_category:
            for document in documents:
                if not isinstance(document, dict):
                    continue
                place_id = str(document.get("id") or "").strip()
                name = str(document.get("place_name") or "").strip()
                if not place_id or not name:
                    continue
                try:
                    point = Coordinates(
                        latitude=float(document["y"]),
                        longitude=float(document["x"]),
                    )
                except (KeyError, TypeError, ValueError):
                    point = None
                try:
                    distance = (
                        int(float(document["distance"]))
                        if document.get("distance") not in (None, "")
                        else None
                    )
                except (TypeError, ValueError):
                    distance = None
                place_url = str(document.get("place_url") or "").strip()
                source = SourceRef(
                    source_id=f"src_kakao_place_{place_id}",
                    source_type="other_public",
                    provider_name="카카오",
                    dataset_name=f"Kakao Local 카테고리 검색 {category_code}",
                    source_record_id=place_id,
                    source_url=place_url if place_url.startswith(("https://", "http://")) else None,
                    retrieved_at=now,
                    limitation="장소 검색 결과이며 운영시간·요금·주차 면수·객실 가능 여부는 보장하지 않습니다.",
                )
                places.append(
                    NearbyPlace(
                        place_id=f"place_kakao_{place_id}",
                        place_type=place_type,
                        name=name,
                        address=str(
                            document.get("road_address_name")
                            or document.get("address_name")
                            or ""
                        ).strip()
                        or None,
                        coordinates=point,
                        distance_m=distance,
                        sources=[source],
                    )
                )

        places.sort(
            key=lambda place: (
                place.distance_m is None,
                place.distance_m or 0,
                place.name,
            )
        )
        self.cache.set(cache_key, places)
        return places

    @property
    def diagnostics(self) -> dict[str, int]:
        stats = self.cache.stats
        return {
            "upstream_calls": self.upstream_calls,
            "cache_hits": stats.hits,
            "cache_misses": stats.misses,
            "cache_entries": stats.entries,
        }
