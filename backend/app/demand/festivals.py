"""TourAPI searchFestival2 일정으로 만드는 D-30 시점 축제 입력. 예측 시점 이후 등록된 축제는 쓰지 않는다."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from app.data_gate.pipeline import normalize_festivals


# 전년도 축제 수는 쓰지 않는다. TourAPI는 현재 등록 정보만 돌려줘 반복 축제의 지난 회차 일정이 사라지기 때문이다.
FESTIVAL_FEATURES = ["festival_active", "festival_days_in_window"]
KNOWN_LEAD_DAYS = 30
WINDOW_DAYS = 3
CALENDAR_COLUMNS = ["event_id", "region_code", "start", "end", "created"]


def calendar_from_items(items: Iterable[dict[str, Any]]) -> pd.DataFrame:
    """TourAPI 원본 item을 (행사, 시군구, 기간, 등록일) 표로 만든다. 등록일·시군구가 없는 행은 뺀다."""
    items = list(items)
    created = {str(item.get("contentid") or item.get("contentId") or "").strip(): str(item.get("createdtime") or "")[:8]
               for item in items}
    rows = []
    for row in normalize_festivals(items):
        stamp = created.get(row["event_id"], "")
        if len(stamp) != 8 or len(row["region_code"]) != 5 or row["region_code"].endswith("000"):
            continue
        rows.append({"event_id": row["event_id"], "region_code": row["region_code"],
                     "start": pd.Timestamp(row["start_date"]), "end": pd.Timestamp(row["end_date"]), "created": pd.Timestamp(stamp)})
    frame = pd.DataFrame(rows, columns=CALENDAR_COLUMNS)
    return frame.drop_duplicates("event_id").reset_index(drop=True)


def load_festival_calendar(paths: Iterable[Path]) -> pd.DataFrame:
    """수집한 searchFestival2 JSONL 페이지들을 축제 일정표로 읽는다."""
    items = []
    for path in paths:
        with Path(path).open(encoding="utf-8") as handle:
            for line in handle:
                items.extend(json.loads(line)["items"])
    return calendar_from_items(items)


def festival_features(target, region_code: str, calendar: pd.DataFrame) -> dict[str, float]:
    """목표일 30일 전까지 등록된 이 시군구 축제만으로 진행 중 축제 수와 전후 3일 축제일 수를 센다."""
    target = pd.Timestamp(target).normalize()
    known = calendar.loc[(calendar.region_code == region_code) & (calendar.created <= target - pd.Timedelta(days=KNOWN_LEAD_DAYS))]
    active = int(((known.start <= target) & (known.end >= target)).sum())
    window = pd.date_range(target - pd.Timedelta(days=WINDOW_DAYS), target + pd.Timedelta(days=WINDOW_DAYS))
    days = sum(bool(((known.start <= day) & (known.end >= day)).any()) for day in window)
    return {"festival_active": float(active), "festival_days_in_window": float(days)}
