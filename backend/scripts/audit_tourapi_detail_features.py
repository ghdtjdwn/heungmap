from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv

from app.data_gate.client import PaginatedPublicDataClient, service_key


ROOT = Path(__file__).resolve().parents[2]
TOURAPI_BASE_URL = "https://apis.data.go.kr/B551011/KorService2"
FIELD_REGISTRY: dict[str, tuple[str, tuple[str, ...]]] = {
    "category_primary": ("common", ("lclsSystm1", "cat1")),
    "category_secondary": ("common", ("lclsSystm2", "cat2")),
    "category_tertiary": ("common", ("lclsSystm3", "cat3")),
    "overview": ("common", ("overview",)),
    "homepage": ("common", ("homepage",)),
    "representative_image": ("common", ("firstimage", "firstimage2")),
    "contact_name": ("common", ("telname",)),
    "event_place": ("intro", ("eventplace",)),
    "operating_time": ("intro", ("playtime",)),
    "primary_sponsor": ("intro", ("sponsor1",)),
    "secondary_sponsor": ("intro", ("sponsor2",)),
    "fee_information": ("intro", ("usetimefestival",)),
    "duration_information": ("intro", ("spendtimefestival",)),
}


def select_audit_sample(
    frame: pd.DataFrame,
    sample_size: int,
    random_state: int = 42,
) -> pd.DataFrame:
    if sample_size < 1:
        raise ValueError("sample_size는 1 이상이어야 합니다.")
    required = {"event_id", "region_code"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"상세 감사 필수 열이 없습니다: {', '.join(missing)}")

    candidates = frame[list(required)].dropna().copy()
    candidates["event_id"] = candidates["event_id"].astype(str)
    candidates["region_code"] = candidates["region_code"].astype(str)
    candidates["metro_code"] = candidates["region_code"].str[:2]
    candidates = candidates.drop_duplicates("event_id").reset_index(drop=True)
    if candidates.empty:
        raise ValueError("감사할 TourAPI event_id가 없습니다.")
    if sample_size >= len(candidates):
        return candidates.sort_values("event_id").reset_index(drop=True)

    metros = candidates["metro_code"].nunique()
    if sample_size < metros:
        return (
            candidates.sample(n=sample_size, random_state=random_state)
            .sort_values("event_id")
            .reset_index(drop=True)
        )

    required_rows = candidates.groupby("metro_code", group_keys=False).sample(
        n=1,
        random_state=random_state,
    )
    remaining = candidates.drop(index=required_rows.index)
    additional = remaining.sample(
        n=sample_size - len(required_rows),
        random_state=random_state,
    )
    return (
        pd.concat([required_rows, additional])
        .sort_values("event_id")
        .reset_index(drop=True)
    )


def _first_value(item: dict[str, Any], aliases: tuple[str, ...]) -> str | None:
    for alias in aliases:
        value = str(item.get(alias) or "").strip()
        if value:
            return value
    return None


def summarize_availability(
    records: list[dict[str, Any]],
    availability_threshold: float = 0.7,
) -> dict[str, Any]:
    if not 0 < availability_threshold <= 1:
        raise ValueError("availability_threshold는 0 초과 1 이하여야 합니다.")
    if not records:
        raise ValueError("요약할 상세 응답이 없습니다.")

    common_responses = sum(bool(record.get("common")) for record in records)
    intro_responses = sum(bool(record.get("intro")) for record in records)
    feature_availability: dict[str, dict[str, Any]] = {}
    for name, (source, aliases) in FIELD_REGISTRY.items():
        values: list[str] = []
        for record in records:
            items = record.get(source) or []
            item = items[0] if items else {}
            value = _first_value(item, aliases)
            if value is not None:
                values.append(value)
        available = len(values)
        rate = available / len(records)
        value_counts = pd.Series(values, dtype="string").value_counts()
        dominant_value_rate = (
            float(value_counts.iloc[0] / available) if available else 0.0
        )
        feature_availability[name] = {
            "source_operation": "detailCommon2" if source == "common" else "detailIntro2",
            "source_fields": list(aliases),
            "available_rows": available,
            "missing_rows": len(records) - available,
            "availability_rate": round(rate, 6),
            "distinct_nonempty_values": len(value_counts),
            "dominant_value_rate": round(dominant_value_rate, 6),
            "candidate_gate_passed": rate >= availability_threshold,
        }

    return {
        "report_version": "1.0",
        "generated_at": datetime.now().astimezone().isoformat(),
        "purpose": "행사 전에 제공되는 TourAPI 상세 필드의 모델 후보 가용성 감사",
        "interpretation": (
            "필드 제공률만 확인하며 지역 방문수요 uplift와의 예측 가치는 별도 검증해야 함"
        ),
        "sample": {
            "events": len(records),
            "metro_codes": len({str(record["metro_code"]) for record in records}),
            "common_response_rate": round(common_responses / len(records), 6),
            "intro_response_rate": round(intro_responses / len(records), 6),
        },
        "availability_threshold": availability_threshold,
        "feature_availability": feature_availability,
        "candidates_passing_availability_gate": [
            name
            for name, result in feature_availability.items()
            if result["candidate_gate_passed"]
        ],
    }


def read_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    records.append(value)
    return records


def append_record(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


async def collect_details(
    sample: pd.DataFrame,
    output: Path,
    request_interval_seconds: float,
) -> list[dict[str, Any]]:
    existing = {str(record.get("event_id")): record for record in read_records(output)}
    key = service_key("TOURAPI_SERVICE_KEY")
    client = PaginatedPublicDataClient(request_interval_seconds=0)
    for position, row in enumerate(sample.itertuples(), start=1):
        event_id = str(row.event_id)
        if event_id in existing:
            continue
        common = await client.fetch_page(
            f"{TOURAPI_BASE_URL}/detailCommon2",
            {"serviceKey": key, "contentId": event_id},
            1,
            10,
        )
        await asyncio.sleep(request_interval_seconds)
        intro = await client.fetch_page(
            f"{TOURAPI_BASE_URL}/detailIntro2",
            {"serviceKey": key, "contentId": event_id, "contentTypeId": "15"},
            1,
            10,
        )
        record = {
            "event_id": event_id,
            "region_code": str(row.region_code),
            "metro_code": str(row.metro_code),
            "retrieved_at": max(common.retrieved_at, intro.retrieved_at),
            "common": common.items,
            "intro": intro.items,
        }
        append_record(output, record)
        existing[event_id] = record
        print(
            json.dumps(
                {
                    "event": position,
                    "sample_size": len(sample),
                    "common_items": len(common.items),
                    "intro_items": len(intro.items),
                },
                ensure_ascii=False,
            )
        )
        await asyncio.sleep(request_interval_seconds)
    return [existing[str(row.event_id)] for row in sample.itertuples()]


def main() -> int:
    parser = argparse.ArgumentParser(description="TourAPI 행사 상세 feature 제공률 감사")
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / "data" / "processed" / "training-table-v1.csv",
    )
    parser.add_argument(
        "--raw-output",
        type=Path,
        default=ROOT / "data" / "raw" / "tourapi-detail-audit.jsonl",
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=ROOT / "data" / "processed" / "tourapi-detail-availability.json",
    )
    parser.add_argument("--sample-size", type=int, default=60)
    parser.add_argument("--availability-threshold", type=float, default=0.7)
    parser.add_argument("--request-interval-seconds", type=float, default=0.25)
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    frame = pd.read_csv(
        args.input,
        dtype={"event_id": "string", "region_code": "string"},
    )
    sample = select_audit_sample(frame, args.sample_size)
    records = asyncio.run(
        collect_details(sample, args.raw_output, args.request_interval_seconds)
    )
    report = summarize_availability(records, args.availability_threshold)
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
