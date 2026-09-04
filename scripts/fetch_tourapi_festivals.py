#!/usr/bin/env python3
"""Collect a small TourAPI festival sample for the HeungMap data gate."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


TOURAPI_ENDPOINT = (
    "https://apis.data.go.kr/B551011/KorService2/searchFestival2"
)
SERVICE_KEY_NAME = "TOURAPI_SERVICE_KEY"
REQUIRED_FIELDS = (
    "contentid",
    "title",
    "eventstartdate",
    "eventenddate",
    "areacode",
    "sigungucode",
)
OPTIONAL_FIELDS = ("addr1", "mapx", "mapy", "firstimage")
SUCCESS_CODES = {"0", "00", "0000"}


class TourApiError(RuntimeError):
    """An error safe to display without exposing the API key."""


def parse_env_file(path: Path) -> dict[str, str]:
    """Read the simple KEY=VALUE form used by this repository's .env file."""
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key.removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def load_service_key(env_file: Path) -> str:
    """Load the TourAPI key without ever printing or persisting it."""
    key = os.environ.get(SERVICE_KEY_NAME, "").strip()
    if not key:
        key = parse_env_file(env_file).get(SERVICE_KEY_NAME, "").strip()
    if not key:
        raise TourApiError(
            f"{SERVICE_KEY_NAME}가 없습니다. .env.example을 .env로 복사한 뒤 "
            "공공데이터포털에서 받은 일반 인증키(Decoding)를 입력하세요."
        )
    return key


def parse_yyyymmdd(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y%m%d")
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"{value!r}은 YYYYMMDD 형식의 유효한 날짜여야 합니다."
        ) from exc


def build_request_url(
    *,
    service_key: str,
    start_date: str,
    end_date: str,
    page: int,
    rows: int,
) -> str:
    query = urlencode(
        {
            "serviceKey": service_key,
            "MobileOS": "ETC",
            "MobileApp": "HeungMap",
            "_type": "json",
            "arrange": "A",
            "eventStartDate": start_date,
            "eventEndDate": end_date,
            "pageNo": page,
            "numOfRows": rows,
        }
    )
    return f"{TOURAPI_ENDPOINT}?{query}"


def fetch_json(url: str, *, timeout: float) -> dict[str, Any]:
    request = Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "HeungMap-data-gate/0.1"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read()
    except HTTPError as exc:
        raise TourApiError(f"TourAPI가 HTTP {exc.code}을 반환했습니다.") from exc
    except URLError as exc:
        reason = getattr(exc, "reason", None)
        reason_name = type(reason).__name__ if reason is not None else "network error"
        raise TourApiError(f"TourAPI 연결에 실패했습니다: {reason_name}") from exc

    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TourApiError("TourAPI 응답이 유효한 UTF-8 JSON이 아닙니다.") from exc
    if not isinstance(decoded, dict):
        raise TourApiError("TourAPI 최상위 응답이 JSON object가 아닙니다.")
    return decoded


def extract_items(payload: Mapping[str, Any]) -> tuple[list[dict[str, Any]], int]:
    response = payload.get("response")
    if not isinstance(response, Mapping):
        raise TourApiError("TourAPI 응답에 response object가 없습니다.")

    header = response.get("header")
    if not isinstance(header, Mapping):
        raise TourApiError("TourAPI 응답에 header object가 없습니다.")
    result_code = str(header.get("resultCode", "")).strip()
    if result_code not in SUCCESS_CODES:
        result_message = str(header.get("resultMsg", "알 수 없는 오류")).strip()
        raise TourApiError(
            f"TourAPI 오류 {result_code or 'unknown'}: {result_message}"
        )

    body = response.get("body")
    if not isinstance(body, Mapping):
        raise TourApiError("TourAPI 응답에 body object가 없습니다.")

    total_count = _as_non_negative_int(body.get("totalCount", 0), "totalCount")
    items_container = body.get("items")
    if items_container in (None, ""):
        return [], total_count
    if not isinstance(items_container, Mapping):
        raise TourApiError("TourAPI body.items 형식을 해석할 수 없습니다.")

    raw_items = items_container.get("item", [])
    if raw_items in (None, ""):
        return [], total_count
    if isinstance(raw_items, Mapping):
        raw_items = [raw_items]
    if not isinstance(raw_items, list) or not all(
        isinstance(item, Mapping) for item in raw_items
    ):
        raise TourApiError("TourAPI body.items.item 형식을 해석할 수 없습니다.")
    return [dict(item) for item in raw_items], total_count


def _as_non_negative_int(value: Any, field_name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise TourApiError(f"TourAPI {field_name}이 정수가 아닙니다.") from exc
    if parsed < 0:
        raise TourApiError(f"TourAPI {field_name}이 음수입니다.")
    return parsed


def is_missing(item: Mapping[str, Any], field: str) -> bool:
    value = item.get(field)
    return value is None or (isinstance(value, str) and not value.strip())


def build_summary(
    *,
    items: Sequence[Mapping[str, Any]],
    total_count: int,
    start_date: str,
    end_date: str,
    page: int,
    rows: int,
    retrieved_at: str,
    raw_path: Path,
) -> dict[str, Any]:
    fields = REQUIRED_FIELDS + OPTIONAL_FIELDS
    missing_counts = {
        field: sum(1 for item in items if is_missing(item, field)) for field in fields
    }
    content_ids = [
        str(item["contentid"]).strip()
        for item in items
        if not is_missing(item, "contentid")
    ]
    required_missing = sum(missing_counts[field] for field in REQUIRED_FIELDS)
    gate_status = (
        "tourapi_sample_ready"
        if items and required_missing == 0 and len(content_ids) == len(set(content_ids))
        else "needs_review"
    )
    return {
        "gate_status": gate_status,
        "source": {
            "provider_name": "한국관광공사",
            "dataset_name": "국문 관광정보 서비스_GW",
            "operation": "searchFestival2",
            "endpoint": TOURAPI_ENDPOINT,
            "retrieved_at": retrieved_at,
        },
        "request": {
            "event_start_date": start_date,
            "event_end_date": end_date,
            "page": page,
            "rows": rows,
        },
        "raw_file": str(raw_path),
        "sample_record_count": len(items),
        "source_total_count": total_count,
        "unique_content_id_count": len(set(content_ids)),
        "duplicate_content_id_count": len(content_ids) - len(set(content_ids)),
        "missing_counts": missing_counts,
        "required_fields": list(REQUIRED_FIELDS),
        "limitations": [
            "이 결과는 TourAPI 축제 표본만 검증한다.",
            (
                "지역별 방문자 데이터 결합과 label 판정은 "
                "아직 수행하지 않았다."
            ),
            "지역 방문자 값을 특정 축제 관람객 수로 해석하지 않는다.",
        ],
    }


def write_json_safely(path: Path, payload: Mapping[str, Any], *, overwrite: bool) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise TourApiError(
            f"출력 파일이 이미 있습니다: {path}. "
            "새 경로를 사용하거나 --overwrite를 지정하세요."
        )
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    ) as temporary:
        json.dump(payload, temporary, ensure_ascii=False, indent=2)
        temporary.write("\n")
        temporary_path = Path(temporary.name)
    temporary_path.replace(path)


def default_paths(
    *, start_date: str, end_date: str, page: int, timestamp: str
) -> tuple[Path, Path]:
    suffix = f"{start_date}_{end_date}_p{page}_{timestamp}"
    return (
        Path("data/raw/tourapi") / f"search_festival_{suffix}.json",
        Path("data/processed/data_gate") / f"tourapi_summary_{suffix}.json",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "TourAPI searchFestival2 표본을 수집하고 필수 필드 누락 요약을 만듭니다. "
            "API key와 생성 데이터는 출력하거나 Git에 포함하지 않습니다."
        )
    )
    parser.add_argument("--start-date", required=True, help="조회 시작일(YYYYMMDD)")
    parser.add_argument("--end-date", required=True, help="조회 종료일(YYYYMMDD)")
    parser.add_argument("--page", type=int, default=1, help="페이지 번호(기본값: 1)")
    parser.add_argument("--rows", type=int, default=100, help="표본 행 수(기본값: 100)")
    parser.add_argument(
        "--timeout", type=float, default=20.0, help="HTTP timeout 초(기본값: 20)"
    )
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--raw-output", type=Path)
    parser.add_argument("--summary-output", type=Path)
    parser.add_argument(
        "--overwrite", action="store_true", help="명시한 기존 출력 파일 덮어쓰기"
    )
    return parser


def validate_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    try:
        start = parse_yyyymmdd(args.start_date)
        end = parse_yyyymmdd(args.end_date)
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))
    if start > end:
        parser.error("--start-date는 --end-date보다 늦을 수 없습니다.")
    if args.page < 1:
        parser.error("--page는 1 이상이어야 합니다.")
    if not 1 <= args.rows <= 1000:
        parser.error("--rows는 1 이상 1000 이하여야 합니다.")
    if args.timeout <= 0:
        parser.error("--timeout은 0보다 커야 합니다.")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    validate_args(args, parser)

    try:
        service_key = load_service_key(args.env_file)
        url = build_request_url(
            service_key=service_key,
            start_date=args.start_date,
            end_date=args.end_date,
            page=args.page,
            rows=args.rows,
        )
        payload = fetch_json(url, timeout=args.timeout)
        items, total_count = extract_items(payload)

        now = datetime.now().astimezone()
        timestamp = now.strftime("%Y%m%dT%H%M%S%z")
        default_raw, default_summary = default_paths(
            start_date=args.start_date,
            end_date=args.end_date,
            page=args.page,
            timestamp=timestamp,
        )
        raw_path = args.raw_output or default_raw
        summary_path = args.summary_output or default_summary
        summary = build_summary(
            items=items,
            total_count=total_count,
            start_date=args.start_date,
            end_date=args.end_date,
            page=args.page,
            rows=args.rows,
            retrieved_at=now.isoformat(timespec="seconds"),
            raw_path=raw_path,
        )

        write_json_safely(raw_path, payload, overwrite=args.overwrite)
        write_json_safely(summary_path, summary, overwrite=args.overwrite)
    except TourApiError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"원본 저장: {raw_path}", file=sys.stderr)
    print(f"요약 저장: {summary_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
