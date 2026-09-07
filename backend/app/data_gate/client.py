from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator
from urllib.parse import unquote

import httpx


TOURAPI_URL = "https://apis.data.go.kr/B551011/KorService2/searchFestival2"
VISITOR_API_URL = "https://apis.data.go.kr/B551011/DataLabService/locgoRegnVisitrDDList"
SUCCESS_CODES = {"0", "00", "0000"}


class DataGateError(RuntimeError):
    def __init__(self, message: str, *, reason: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.reason = reason
        self.retryable = retryable


@dataclass(frozen=True)
class Page:
    items: list[dict[str, Any]]
    page_no: int
    total_count: int
    retrieved_at: str


def service_key(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise DataGateError(f"{name}가 설정되지 않았습니다.", reason="not_configured")
    # httpx encodes query parameters. Decode portal-provided encoded keys once.
    return unquote(value)


def _parse_page(payload: Any, page_no: int) -> Page:
    try:
        response = payload["response"]
        header = response["header"]
        body = response["body"]
    except (KeyError, TypeError) as exc:
        raise DataGateError("공공데이터 응답 형식을 해석하지 못했습니다.", reason="invalid_response") from exc
    code = str(header.get("resultCode", ""))
    if code not in SUCCESS_CODES:
        message = str(header.get("resultMsg", "API 오류"))
        reason = "quota" if code in {"22", "23"} else "permission" if code in {"20", "30", "31"} else "upstream"
        raise DataGateError(f"공공데이터 API 오류({code}): {message}", reason=reason, retryable=reason in {"quota", "upstream"})
    raw_items = (body.get("items") or {}).get("item") or []
    if isinstance(raw_items, dict):
        raw_items = [raw_items]
    if not isinstance(raw_items, list):
        raise DataGateError("공공데이터 목록 형식이 올바르지 않습니다.", reason="invalid_response")
    return Page(
        items=[item for item in raw_items if isinstance(item, dict)],
        page_no=page_no,
        total_count=int(body.get("totalCount") or 0),
        retrieved_at=datetime.now().astimezone().isoformat(),
    )


class PaginatedPublicDataClient:
    def __init__(
        self,
        *,
        timeout_seconds: float = 12,
        max_retries: int = 2,
        request_interval_seconds: float = 0.25,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.request_interval_seconds = request_interval_seconds
        self.transport = transport

    async def fetch_page(self, url: str, params: dict[str, Any], page_no: int, rows: int) -> Page:
        query = {
            **params,
            "pageNo": page_no,
            "numOfRows": rows,
            "MobileOS": "ETC",
            "MobileApp": "HeungMapDataGate",
            "_type": "json",
        }
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds, transport=self.transport) as client:
                    response = await client.get(url, params=query)
                if response.status_code == 429:
                    raise DataGateError("공공데이터 API 호출 한도에 도달했습니다.", reason="quota", retryable=True)
                if response.status_code >= 500:
                    raise DataGateError(f"공공데이터 API가 HTTP {response.status_code}을 반환했습니다.", reason="upstream", retryable=True)
                if response.status_code in {401, 403}:
                    raise DataGateError("공공데이터 API 활용 권한을 확인해 주세요.", reason="permission")
                response.raise_for_status()
                return _parse_page(response.json(), page_no)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                error = DataGateError("공공데이터 API 응답 시간이 초과됐습니다.", reason="timeout", retryable=True)
                error.__cause__ = exc
            except (httpx.HTTPError, ValueError) as exc:
                error = DataGateError("공공데이터 API 응답을 읽지 못했습니다.", reason="invalid_response")
                error.__cause__ = exc
            except DataGateError as exc:
                error = exc
            if not error.retryable or attempt >= self.max_retries:
                raise error
            await asyncio.sleep(min(2**attempt, 4))
        raise AssertionError("retry loop must return or raise")

    async def iter_pages(
        self,
        url: str,
        params: dict[str, Any],
        *,
        rows: int = 100,
        max_pages: int = 50,
        resume_after_page: int = 0,
    ) -> AsyncIterator[Page]:
        for page_no in range(resume_after_page + 1, max_pages + 1):
            page = await self.fetch_page(url, params, page_no, rows)
            yield page
            if page_no * rows >= page.total_count or not page.items:
                break
            await asyncio.sleep(self.request_interval_seconds)


def append_page(path: Path, page: Page, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "source": source,
        "retrieved_at": page.retrieved_at,
        "page_no": page.page_no,
        "total_count": page.total_count,
        "items": page.items,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def completed_page(path: Path) -> int:
    if not path.exists():
        return 0
    last_page = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                last_page = max(last_page, int(json.loads(line).get("page_no", 0)))
            except (ValueError, TypeError, json.JSONDecodeError):
                continue
    return last_page
