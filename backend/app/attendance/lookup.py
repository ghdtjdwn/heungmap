"""문체부 연도별 지역축제 자료의 전년도 보고 방문객을 행사 근거(실제값)로 찾는다. 예측값이 아니며 퍼지 매칭을 하지 않는다."""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import pandas as pd

from app.attendance.data import SOURCE_URL, canonical_title, load_archives, normalize_province
from app.schemas import Evidence, RegionRef, SourceRef


DEFAULT_PATH = Path(__file__).resolve().parents[3] / "data" / "processed" / "mcst-attendance-lookup.csv"
COLUMNS = ["plan_year", "province", "district", "title", "lookup_key", "prior_attendance", "measurement"]
# 법정동 시도 코드 → 문체부 광역 표기. 강원(42→51)·전북(45→52) 신·구 코드를 모두 받는다.
ADMIN_TO_PROVINCE = {
    "11": "서울", "26": "부산", "27": "대구", "28": "인천", "29": "광주", "30": "대전", "31": "울산", "36": "세종",
    "41": "경기", "42": "강원", "51": "강원", "43": "충북", "44": "충남", "45": "전북", "52": "전북", "46": "전남",
    "47": "경북", "48": "경남", "50": "제주",
}
MAX_RESULT_AGE_YEARS = 3  # 오래된 실적은 현재 규모를 오해하게 하므로 최근 3년 실적만 보여 준다.
logger = logging.getLogger(__name__)


def lookup_key(title: str) -> str:
    """회차·연도(`2026년` 포함)를 지운 정확 비교용 축제명."""
    return canonical_title(re.sub(r"(?:19|20)\d{2}\s*년", "", str(title or "")))


def build_lookup(archives: Iterable[Path]) -> tuple[pd.DataFrame, dict]:
    """축제별 가장 최근 계획연도의 양수 전년도 방문객만 남긴다. 담당자 성명·연락처는 원래 읽지 않는다."""
    records, audit = load_archives(archives)
    frame = records.loc[records.prior_attendance.fillna(0) > 0].copy()
    frame["lookup_key"] = frame.title.map(lookup_key)
    frame = frame.loc[(frame.lookup_key.str.len() >= 2) & (frame.province != "unknown")]
    frame = frame.sort_values("plan_year").drop_duplicates(["province", "district", "lookup_key"], keep="last")
    return frame[COLUMNS].reset_index(drop=True), {**audit, "lookup_rows": len(frame)}


def _province(region: RegionRef) -> str | None:
    code = region.legal_dong_code or ""
    if len(code) >= 2 and code[:2] in ADMIN_TO_PROVINCE:
        return ADMIN_TO_PROVINCE[code[:2]]
    first = (region.display_name or "").split()[:1]
    province = normalize_province(first[0]) if first else "unknown"
    return None if province == "unknown" else province


def lookup_previous_attendance(*, title: str | None, region: RegionRef | None, table: pd.DataFrame,
                               min_result_year: int | None = None) -> dict | None:
    """같은 광역·같은 시군구(또는 광역 주관)·같은 정규화 축제명인 한 건만 돌려준다. 없거나 모호하면 None."""
    key = lookup_key(title or "")
    province = _province(region) if region else None
    if len(key) < 2 or not province:
        return None
    names = {token for token in (region.display_name or "").split() if token.endswith(("시", "군", "구"))}
    candidates = table.loc[(table.lookup_key == key) & (table.province == province)
                           & (table.district.fillna("").isin(names) | (table.district.fillna("") == ""))]
    if min_result_year is not None:
        candidates = candidates.loc[candidates.plan_year - 1 >= min_result_year]
    if candidates.empty:
        return None
    local = candidates.loc[candidates.district.fillna("") != ""]
    candidates = local if not local.empty else candidates
    if candidates[["district"]].drop_duplicates().shape[0] > 1:
        return None
    return candidates.sort_values("plan_year").iloc[-1].to_dict()


@lru_cache(maxsize=2)
def _table(path: str, mtime: int) -> tuple[pd.DataFrame, datetime]:
    table = pd.read_csv(path, dtype={"district": str, "province": str, "lookup_key": str})
    table["district"] = table.district.fillna("")
    return table, datetime.fromtimestamp(mtime / 1e9, tz=timezone.utc)


def load_table() -> tuple[pd.DataFrame, datetime] | None:
    path = Path(os.environ.get("HEUNGMAP_MCST_LOOKUP_PATH", str(DEFAULT_PATH)))
    try:
        return _table(str(path), path.stat().st_mtime_ns)
    except (OSError, ValueError, KeyError):
        logger.warning("문체부 전년 방문객 표를 불러오지 못해 근거에서 생략합니다.")
        return None


def prior_attendance_evidence(title: str | None, region: RegionRef | None) -> tuple[Evidence, SourceRef] | None:
    """행사 근거로 붙일 문체부 전년 실적. 표가 없거나 정확 일치가 없으면 None."""
    loaded = load_table()
    if loaded is None:
        return None
    table, built_at = loaded
    record = lookup_previous_attendance(title=title, region=region, table=table,
                                        min_result_year=datetime.now().year - MAX_RESULT_AGE_YEARS)
    if record is None:
        return None
    year = int(record["plan_year"]) - 1
    measurement = record["measurement"] if record["measurement"] not in {"미제공", ""} else "집계방식 미제공"
    source = SourceRef(source_id="src_mcst_festivals", source_type="other_public", provider_name="문화체육관광부",
                       dataset_name="연도별 지역축제 정보", source_url=SOURCE_URL, retrieved_at=built_at,
                       limitation="주최 측이 문체부에 제출한 값입니다.")
    evidence = Evidence(evidence_id="ev_mcst_prior_attendance", value_type="verified_fact", label="문체부 보고 전년 방문객",
                        display_value=f"{float(record['prior_attendance']):,.0f}명 ({year}년 실적, {measurement})",
                        numeric_value=float(record["prior_attendance"]), unit="people", source_refs=[source.source_id],
                        limitation="주최 측이 문체부에 제출한 전년도 방문객이며 집계 방식이 축제마다 다릅니다. 흥할지도의 예측값이 아닙니다.")
    return evidence, source


def attach_prior_attendance(prediction, evidence_list: list | None, title: str | None, region: RegionRef | None):
    """예측이 available이면 예측 근거에, evidence_list가 있으면 그 목록에도 문체부 실적을 붙인다."""
    found = prior_attendance_evidence(title, region)
    if found is None:
        return prediction
    evidence, source = found
    if getattr(prediction, "status", None) == "available":
        if all(item.evidence_id != evidence.evidence_id for item in prediction.evidence):
            prediction.evidence.append(evidence)
        if all(item.source_id != source.source_id for item in prediction.sources):
            prediction.sources.append(source)
    if evidence_list is not None and all(item.evidence_id != evidence.evidence_id for item in evidence_list):
        evidence_list.append(evidence)
    return prediction


def write_lookup(table: pd.DataFrame, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(output, index=False)


def summary_json(table: pd.DataFrame, audit: dict) -> str:
    return json.dumps({"rows": len(table), "plan_years": sorted(table.plan_year.unique().tolist()),
                       "measurement_counts": table.measurement.value_counts().to_dict(), "archive_records": audit.get("records")},
                      ensure_ascii=False, indent=2)
