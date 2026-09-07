from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import median
from typing import Any, Iterable


TOUR_AREA_TO_ADMIN = {
    "1": "11", "2": "28", "3": "30", "4": "27", "5": "29", "6": "26", "7": "31", "8": "36",
    "31": "41", "32": "51", "33": "43", "34": "44", "35": "47", "36": "48", "37": "45", "38": "46", "39": "50",
}
POST_EVENT_FIELDS = {
    "actual_attendance", "actual_revenue", "event_period_visitors", "post_event_sns_mentions",
    "post_event_search_volume", "event_period_card_sales", "label_value",
}


def read_jsonl_pages(path: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            page = json.loads(line)
            retrieved_at = page.get("retrieved_at")
            for item in page.get("items", []):
                if isinstance(item, dict):
                    items.append({**item, "_retrieved_at": retrieved_at})
    return items


def import_visitor_csv(path: Path) -> list[dict[str, Any]]:
    """Import an official DataLab export without fixing one Korean/English header spelling."""
    aliases = {
        "date": ("baseYmd", "기준일자", "날짜", "date"),
        "region_code": ("signguCode", "signguCd", "areaCode", "areaCd", "지역코드", "region_code"),
        "region_name": ("signguNm", "areaNm", "지역명", "region_name"),
        "visitor_type": ("touDivNm", "방문자구분", "visitor_type"),
        "visitor_count": ("touNum", "방문자수", "visitor_count"),
    }
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for raw in csv.DictReader(handle):
            normalized: dict[str, Any] = {}
            for target, candidates in aliases.items():
                normalized[target] = next((raw.get(name) for name in candidates if raw.get(name) not in (None, "")), None)
            if normalized["date"] and normalized["visitor_count"] is not None:
                try:
                    normalized["visitor_count"] = float(str(normalized["visitor_count"]).replace(",", ""))
                except ValueError:
                    continue
                rows.append(normalized)
    return rows


def normalize_festivals(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        content_id = str(row.get("contentid") or row.get("contentId") or "").strip()
        title = str(row.get("title") or "").strip()
        start = str(row.get("eventstartdate") or row.get("eventStartDate") or "")[:8]
        end = str(row.get("eventenddate") or row.get("eventEndDate") or start)[:8]
        legal_region = str(row.get("lDongRegnCd") or row.get("ldongregncd") or "").strip()
        legal_sigungu = str(row.get("lDongSignguCd") or row.get("ldongsigngucd") or "").strip()
        area = str(row.get("areacode") or row.get("areaCode") or "").strip()
        if len(legal_region) == 5:
            region_code = legal_region
        elif len(legal_sigungu) == 5:
            region_code = legal_sigungu
        elif len(legal_region) == 2 and len(legal_sigungu) == 3:
            region_code = f"{legal_region}{legal_sigungu}"
        else:
            region_code = legal_region or TOUR_AREA_TO_ADMIN.get(area, area)
        if not (content_id and title and len(start) == 8 and len(end) == 8 and region_code):
            continue
        result.append({
            "event_id": content_id,
            "title": title,
            "start_date": start,
            "end_date": end,
            "tour_area_code": area,
            "region_code": region_code,
            "sigungu_code": legal_sigungu or str(row.get("sigungucode") or row.get("sigunguCode") or "").strip() or None,
            "address": str(row.get("addr1") or "").strip() or None,
            "latitude": row.get("mapy"),
            "longitude": row.get("mapx"),
            "retrieved_at": row.get("_retrieved_at"),
        })
    return result


def normalize_visitors(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    daily: dict[tuple[str, str], float] = defaultdict(float)
    names: dict[tuple[str, str], str | None] = {}
    for row in rows:
        raw_date = str(row.get("date") or row.get("baseYmd") or "")[:8]
        region_code = str(row.get("region_code") or row.get("signguCode") or row.get("signguCd") or row.get("areaCode") or row.get("areaCd") or "").strip()
        try:
            count = float(row.get("visitor_count") if row.get("visitor_count") is not None else row.get("touNum"))
            datetime.strptime(raw_date, "%Y%m%d")
        except (TypeError, ValueError):
            continue
        key = (raw_date, region_code)
        daily[key] += count
        names[key] = str(row.get("region_name") or row.get("signguNm") or row.get("areaNm") or "").strip() or None
    return [{"date": d, "region_code": r, "region_name": names[(d, r)], "visitor_count": value} for (d, r), value in sorted(daily.items())]


def join_labels(festivals: list[dict[str, Any]], visitors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_region_date = {(row["region_code"], row["date"]): row["visitor_count"] for row in visitors}
    joined: list[dict[str, Any]] = []
    for event in festivals:
        start = datetime.strptime(event["start_date"], "%Y%m%d").date()
        end = datetime.strptime(event["end_date"], "%Y%m%d").date()
        if end < start:
            continue
        region = event["region_code"]
        event_days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
        baseline_days = [start - timedelta(days=i) for i in range(1, 29)]
        event_values = [by_region_date[(region, day.strftime("%Y%m%d"))] for day in event_days if (region, day.strftime("%Y%m%d")) in by_region_date]
        baseline_values = [by_region_date[(region, day.strftime("%Y%m%d"))] for day in baseline_days if (region, day.strftime("%Y%m%d")) in by_region_date]
        if len(event_values) != len(event_days) or len(baseline_values) < 14:
            continue
        level = sum(event_values) / len(event_values)
        baseline = median(baseline_values)
        uplift = level - baseline
        uplift_rate = uplift / baseline if baseline else None
        joined.append({
            **event,
            "label_type": "regional_daily_visitor_uplift_rate",
            "label_unit": "ratio_vs_prior_28d_median",
            "event_window_daily_mean": round(level, 3),
            "baseline_prior_28d_median": round(baseline, 3),
            "uplift_absolute": round(uplift, 3),
            "uplift_rate": round(uplift_rate, 6) if uplift_rate is not None else None,
            "regional_congestion_index": round((level / baseline) * 100, 3) if baseline else None,
        })
    return joined


def assert_no_post_event_features(feature_names: Iterable[str]) -> None:
    leaked = sorted(set(feature_names) & POST_EVENT_FIELDS)
    if leaked:
        raise ValueError(f"기획 시점 이후 정보가 feature에 포함됐습니다: {', '.join(leaked)}")


def build_quality_report(festival_rows: list[dict[str, Any]], visitor_rows: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    normalized_festivals = normalize_festivals(festival_rows)
    unique_festivals: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in normalized_festivals:
        unique_festivals.setdefault((row["event_id"], row["start_date"], row["end_date"]), row)
    festivals = list(unique_festivals.values())
    visitors = normalize_visitors(visitor_rows)
    joined = join_labels(festivals, visitors)
    keys = [(row["event_id"], row["start_date"], row["end_date"]) for row in normalized_festivals]
    duplicates = sum(count - 1 for count in Counter(keys).values() if count > 1)
    missing_coordinates = sum(not row.get("latitude") or not row.get("longitude") for row in festivals)
    years = sorted({row["start_date"][:4] for row in festivals})
    regions = sorted({row["region_code"] for row in festivals})
    join_rate = len(joined) / len(festivals) if festivals else 0.0
    gate_passed = len(festivals) >= 50 and len(joined) >= 50 and join_rate >= 0.7
    report = {
        "report_version": "1.0",
        "generated_at": datetime.now().astimezone().isoformat(),
        "festival_rows_raw": len(festival_rows),
        "festival_rows_valid": len(festivals),
        "visitor_rows_raw": len(visitor_rows),
        "visitor_rows_valid_daily": len(visitors),
        "joined_rows": len(joined),
        "join_rate": round(join_rate, 6),
        "duplicate_rate": round(duplicates / len(normalized_festivals), 6) if normalized_festivals else 0.0,
        "missing_coordinate_rate": round(missing_coordinates / len(festivals), 6) if festivals else 0.0,
        "year_range": [years[0], years[-1]] if years else [],
        "region_codes": regions,
        "label_candidates": [
            {"name": "event_window_daily_mean", "unit": "regional visitor-days/day", "risk": "특정 축제 관람객 수가 아님"},
            {"name": "uplift_absolute", "unit": "regional visitor-days/day vs prior 28-day median", "risk": "동시 행사·계절 변화 포함"},
            {"name": "uplift_rate", "unit": "ratio", "risk": "낮은 baseline 지역에서 변동 확대"},
            {"name": "regional_congestion_index", "unit": "index baseline=100", "risk": "상대 지역 방문수요이며 실제 혼잡 관측이 아님"},
        ],
        "recommended_label": "regional_daily_visitor_uplift_rate" if gate_passed else None,
        "gate_passed": gate_passed,
        "blocker": None if gate_passed else "실제 지역 방문자 일별 데이터와 50개 이상의 70% 결합 표본이 필요합니다.",
        "leakage_risks": ["행사 기간 방문자·소비·검색량을 입력 feature로 사용하면 label 누수", "미래 기간으로 계산한 이동평균·지역 순위"],
        "interpretation": "지역 방문자 집계는 특정 축제 관람객 수가 아니며 일별 방문자-일 수치입니다.",
    }
    return report, joined


def write_outputs(report: dict[str, Any], joined: list[dict[str, Any]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "quality-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if joined:
        with (output_dir / "training-table-v1.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(joined[0]))
            writer.writeheader()
            writer.writerows(joined)
