from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from app.data_gate.client import (
    TOURAPI_URL,
    VISITOR_API_URL,
    DataGateError,
    PaginatedPublicDataClient,
    append_page,
    completed_page,
    service_key,
)
from app.data_gate.pipeline import build_quality_report, import_visitor_csv, read_jsonl_pages, write_outputs


ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")


async def collect(kind: str, start: str, end: str, output: Path, max_pages: int, rows: int) -> None:
    if kind == "festivals":
        url = TOURAPI_URL
        key_name = "TOURAPI_SERVICE_KEY"
        params = {"serviceKey": service_key(key_name), "eventStartDate": start, "eventEndDate": end, "arrange": "A"}
    else:
        url = VISITOR_API_URL
        key_name = "VISITOR_API_SERVICE_KEY"
        params = {"serviceKey": service_key(key_name), "startYmd": start, "endYmd": end}
    client = PaginatedPublicDataClient()
    resume = completed_page(output)
    async for page in client.iter_pages(url, params, rows=rows, max_pages=max_pages, resume_after_page=resume):
        append_page(output, page, kind)
        print(json.dumps({"source": kind, "page": page.page_no, "items": len(page.items), "total": page.total_count, "retrieved_at": page.retrieved_at}, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser(description="흥할지도 데이터 게이트 수집·결합")
    sub = parser.add_subparsers(dest="command", required=True)
    collect_parser = sub.add_parser("collect")
    collect_parser.add_argument("kind", choices=["festivals", "visitors"])
    collect_parser.add_argument("--start", required=True, help="YYYYMMDD")
    collect_parser.add_argument("--end", required=True, help="YYYYMMDD")
    collect_parser.add_argument("--output", type=Path, required=True)
    collect_parser.add_argument("--max-pages", type=int, default=50)
    collect_parser.add_argument("--rows", type=int, default=100, choices=range(1, 10001), metavar="1..10000")
    build_parser = sub.add_parser("build")
    build_parser.add_argument("--festivals", type=Path, nargs="+", required=True)
    visitors = build_parser.add_mutually_exclusive_group(required=True)
    visitors.add_argument("--visitors-jsonl", type=Path, nargs="+")
    visitors.add_argument("--visitors-csv", type=Path)
    build_parser.add_argument("--output-dir", type=Path, default=ROOT / "data" / "processed")
    args = parser.parse_args()
    try:
        if args.command == "collect":
            date.fromisoformat(f"{args.start[:4]}-{args.start[4:6]}-{args.start[6:8]}")
            date.fromisoformat(f"{args.end[:4]}-{args.end[4:6]}-{args.end[6:8]}")
            asyncio.run(collect(args.kind, args.start, args.end, args.output, args.max_pages, args.rows))
        else:
            festival_rows = [row for path in args.festivals for row in read_jsonl_pages(path)]
            visitor_rows = (
                [row for path in args.visitors_jsonl for row in read_jsonl_pages(path)]
                if args.visitors_jsonl
                else import_visitor_csv(args.visitors_csv)
            )
            report, joined = build_quality_report(festival_rows, visitor_rows)
            write_outputs(report, joined, args.output_dir)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if report["gate_passed"] else 2
    except (DataGateError, ValueError, OSError) as exc:
        reason = getattr(exc, "reason", "invalid_input")
        print(json.dumps({"status": "error", "reason": reason, "message": str(exc)}, ensure_ascii=False))
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
