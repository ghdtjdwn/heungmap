from __future__ import annotations

import os
from hashlib import sha256
from datetime import datetime
from typing import Any

import httpx

from app.schemas import AddressSearchItem, Coordinates, SourceRef


BASE_URL = "https://dapi.kakao.com/v2/local/search/address.json"


class KakaoAddressUnavailable(RuntimeError):
    pass


class KakaoAddressClient:
    def __init__(self, rest_api_key: str | None = None, timeout_seconds: float = 6.0) -> None:
        self.rest_api_key = (rest_api_key or os.getenv("KAKAO_REST_API_KEY", "")).strip()
        self.timeout_seconds = timeout_seconds

    @property
    def configured(self) -> bool:
        return bool(self.rest_api_key)

    async def search_addresses(self, *, query: str, limit: int = 10) -> list[AddressSearchItem]:
        if not self.rest_api_key:
            raise KakaoAddressUnavailable("KAKAO_REST_API_KEY가 설정되지 않았습니다.")
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(
                    BASE_URL,
                    params={"query": query, "page": 1, "size": limit, "analyze_type": "similar"},
                    headers={"Authorization": f"KakaoAK {self.rest_api_key}"},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise KakaoAddressUnavailable("카카오 주소 검색을 불러오지 못했습니다.") from exc

        documents = payload.get("documents") if isinstance(payload, dict) else None
        if not isinstance(documents, list):
            raise KakaoAddressUnavailable("카카오 주소 검색 응답 형식을 해석하지 못했습니다.")

        now = datetime.now().astimezone()
        results: list[AddressSearchItem] = []
        for document in documents:
            if not isinstance(document, dict):
                continue
            road = document.get("road_address") if isinstance(document.get("road_address"), dict) else {}
            jibun = document.get("address") if isinstance(document.get("address"), dict) else {}
            road_name = str(road.get("address_name") or "").strip() or None
            jibun_name = str(jibun.get("address_name") or document.get("address_name") or "").strip() or None
            address_name = road_name or jibun_name
            if not address_name:
                continue
            try:
                coordinates = Coordinates(
                    latitude=float(document["y"]),
                    longitude=float(document["x"]),
                )
            except (KeyError, TypeError, ValueError):
                continue
            building_name = str(road.get("building_name") or "").strip() or None
            record_hash = sha256(
                f"{address_name}|{document.get('x')}|{document.get('y')}".encode("utf-8")
            ).hexdigest()[:16]
            source = SourceRef(
                source_id=f"src_kakao_address_{record_hash}",
                source_type="other_public",
                provider_name="카카오",
                dataset_name="Kakao Local 주소 검색",
                source_record_id=None,
                retrieved_at=now,
                limitation="주소와 좌표 검색 결과이며 장소 운영 상태·수용인원·시설 정보는 포함하지 않습니다.",
            )
            results.append(
                AddressSearchItem(
                    address_name=address_name,
                    road_address_name=road_name,
                    jibun_address_name=jibun_name,
                    building_name=building_name,
                    coordinates=coordinates,
                    source=source,
                )
            )
        return results[:limit]
