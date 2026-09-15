"""Strict, reproducible regional-demand data and pre-event feature construction.

The backtest assumes a 30-day planning lead and a 30-day publication lag. Raw
responses were collected retrospectively: neither API's historical publication
or revision state can be established from these snapshots.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from app.data_gate.pipeline import normalize_festivals


LEAD_DAYS = 30
PUBLICATION_LAG_DAYS = 30
HISTORY_DAYS = 84
MAX_DURATION_DAYS = 30
FEATURE_VERSION = "regional-history-d30-v1"
FEATURES = [
    "month_sin", "month_cos", "duration_days",
    *[f"weekday_{day}_fraction" for day in range(7)],
    "calendar_expected_uplift", "history_trend_28d", "history_volatility",
    "history_weekend_ratio", "log_history_level", "province_code",
]
DAILY_COLUMNS = ["date", "region_code", "region_name", "visitor_count", "retrieved_at"]


class InsufficientHistoryError(ValueError):
    """A complete, positive pre-event history cannot be constructed."""


def _date(value: Any) -> pd.Timestamp:
    if isinstance(value, (date, datetime, pd.Timestamp)):
        result = pd.Timestamp(value)
    else:
        text = str(value)
        pattern = "%Y%m%d" if re.fullmatch(r"[0-9]{8}", text) else "%Y-%m-%d"
        result = pd.Timestamp(datetime.strptime(text, pattern))
    if pd.isna(result) or result.tzinfo is not None or result != result.normalize():
        raise ValueError("날짜에는 유효한 현지 달력 날짜만 사용할 수 있습니다.")
    return result


def _pages(paths: Iterable[Path]) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    retrieved: list[str] = []
    for path in paths:
        with Path(path).open(encoding="utf-8") as handle:
            for line in handle:
                page = json.loads(line)
                timestamp = page.get("retrieved_at")
                if not timestamp or pd.isna(pd.to_datetime(timestamp, utc=True, errors="coerce")):
                    raise ValueError("원본 페이지에 유효한 수집 시각이 없습니다.")
                if not isinstance(page.get("items"), list):
                    raise ValueError("원본 페이지의 목록 형식이 잘못됐습니다.")
                retrieved.append(timestamp)
                for item in page["items"]:
                    if not isinstance(item, dict):
                        raise ValueError("원본 레코드 형식이 잘못됐습니다.")
                    records.append({**item, "_retrieved_at": timestamp})
    return records, retrieved


def load_daily_visitors(paths: Iterable[Path]) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Deduplicate visitor types before summing complete three-type days.

    Conflicting duplicate counts and invalid numeric values fail the build.
    Partial days are omitted rather than treated as smaller observed totals.
    """
    records, retrieved = _pages(paths)
    rows: list[dict[str, Any]] = []
    discarded: Counter[str] = Counter()
    for raw in records:
        try:
            count = float(raw["touNum"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("방문자 수는 유한한 비음수여야 합니다.") from exc
        if not np.isfinite(count) or count < 0:
            raise ValueError("방문자 수는 유한한 비음수여야 합니다.")
        region = str(raw.get("signguCode", "")).strip()
        if not re.fullmatch(r"[0-9]{5}", region) or region.endswith("000"):
            discarded["non_sigungu_rows"] += 1
            continue
        visitor_type = str(raw.get("touDivCd", ""))
        if visitor_type not in {"1", "2", "3"}:
            discarded["unsupported_visitor_type_rows"] += 1
            continue
        try:
            observed_date = _date(raw.get("baseYmd", ""))
        except (TypeError, ValueError) as exc:
            raise ValueError("방문자 기준일이 잘못됐습니다.") from exc
        rows.append({
            "date": observed_date, "region_code": region, "visitor_type": visitor_type,
            "region_name": str(raw.get("signguNm", "")).strip(),
            "visitor_count": count, "retrieved_at": raw["_retrieved_at"],
        })
    if not rows:
        raise ValueError("검증 가능한 방문자 원본이 없습니다.")
    frame = pd.DataFrame(rows)
    keys = ["date", "region_code", "visitor_type"]
    duplicates = frame.duplicated(keys, keep=False)
    if (frame.loc[duplicates].groupby(keys)["visitor_count"].nunique() > 1).any():
        raise ValueError("동일 날짜·지역·방문자 구분의 값이 충돌합니다.")
    duplicate_count = int(frame.duplicated(keys).sum())
    # A repeated response is the same observation, never additional visitors.
    frame = frame.sort_values("retrieved_at").drop_duplicates(keys, keep="first")
    daily = frame.groupby(["date", "region_code"], as_index=False).agg(
        visitor_count=("visitor_count", "sum"),
        visitor_types=("visitor_type", "nunique"),
        region_name=("region_name", "last"),
        retrieved_at=("retrieved_at", "max"),
    )
    incomplete_count = int((daily["visitor_types"] != 3).sum())
    daily = daily.loc[daily["visitor_types"] == 3, DAILY_COLUMNS].reset_index(drop=True)
    if daily.empty or not np.isfinite(daily["visitor_count"]).all():
        raise ValueError("합산한 일별 방문자 데이터가 비어 있거나 유한하지 않습니다.")
    return daily, {
        "raw_rows": len(records), "duplicate_type_rows_removed": duplicate_count,
        "incomplete_type_days_discarded": incomplete_count,
        "discarded_rows": dict(discarded), "daily_rows": len(daily),
        "regions": int(daily["region_code"].nunique()),
        "date_min": daily["date"].min().date().isoformat(),
        "date_max": daily["date"].max().date().isoformat(),
        "retrieved_at_min": min(retrieved), "retrieved_at_max": max(retrieved),
    }


def _history_window(start: pd.Timestamp, region_code: str, history: pd.DataFrame) -> pd.Series:
    cutoff = start - pd.Timedelta(days=LEAD_DAYS + PUBLICATION_LAG_DAYS)
    dates = pd.date_range(end=cutoff, periods=HISTORY_DAYS)
    selected = history.loc[history["region_code"].astype(str) == str(region_code), ["date", "visitor_count"]]
    selected = selected.assign(date=pd.to_datetime(selected["date"]))
    selected = selected.loc[selected["date"].isin(dates)]
    if selected["date"].duplicated().any():
        raise ValueError("일별 방문자 이력에 중복 날짜가 있습니다.")
    values = selected.set_index("date")["visitor_count"].reindex(dates).astype(float)
    if len(values.dropna()) != HISTORY_DAYS:
        raise InsufficientHistoryError("예측 기준 이전의 연속 84일 방문자 이력이 필요합니다.")
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("이력의 방문자 수는 유한한 비음수여야 합니다.")
    if min(float(values.median()), float(values.iloc[-28:].median()), float(values.iloc[-56:-28].median())) <= 0:
        raise InsufficientHistoryError("비율 계산을 위한 양의 지역 방문자 기준선이 필요합니다.")
    return values


def make_features(
    start_date: date | str | pd.Timestamp,
    end_date: date | str | pd.Timestamp,
    region_code: str,
    history_frame: pd.DataFrame,
) -> dict[str, float]:
    """Use calendar inputs and only observations on/before event start minus 60d."""
    start, end = _date(start_date), _date(end_date)
    duration = (end - start).days + 1
    if not 1 <= duration <= MAX_DURATION_DAYS:
        raise ValueError("학습·추론 지원 행사 기간은 1~30일입니다.")
    if not re.fullmatch(r"[0-9]{5}", str(region_code)) or str(region_code).endswith("000"):
        raise ValueError("5자리 기초지자체 코드가 필요합니다.")
    history = _history_window(start, str(region_code), history_frame)
    weekdays = pd.date_range(start, end).dayofweek
    weekday_profile = history.groupby(history.index.dayofweek).median()
    weekend = float(history.loc[history.index.dayofweek >= 5].median())
    weekday = float(history.loc[history.index.dayofweek < 5].median())
    if weekday <= 0:
        raise InsufficientHistoryError("평일 방문자 기준선은 양수여야 합니다.")
    angle = 2 * np.pi * (start.month - 1) / 12
    result = {
        "month_sin": float(np.sin(angle)), "month_cos": float(np.cos(angle)),
        "duration_days": float(duration),
        **{f"weekday_{day}_fraction": float(np.mean(weekdays == day)) for day in range(7)},
        "calendar_expected_uplift": float(weekday_profile.reindex(weekdays).mean() / history.median() - 1),
        "history_trend_28d": float(history.iloc[-28:].median() / history.iloc[-56:-28].median() - 1),
        "history_volatility": float(history.std(ddof=0) / history.mean()),
        "history_weekend_ratio": weekend / weekday,
        "log_history_level": float(np.log1p(history.iloc[-28:].median())),
        "province_code": float(str(region_code)[:2]),
    }
    if not np.isfinite(list(result.values())).all():
        raise ValueError("계산한 모델 입력이 유한하지 않습니다.")
    return result


def build_training_dataset(
    festival_paths: Iterable[Path], visitor_paths: Iterable[Path],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    daily, visitor_audit = load_daily_visitors(visitor_paths)
    raw, retrieved = _pages(festival_paths)
    normalized = normalize_festivals(raw)
    events: dict[tuple[str, str, str], dict[str, Any]] = {}
    excluded: Counter[str] = Counter()
    for event in normalized:
        key = (event["event_id"], event["start_date"], event["end_date"])
        if key in events:
            if events[key]["region_code"] != event["region_code"]:
                raise ValueError("동일 행사 회차의 지역 코드가 충돌합니다.")
            excluded["duplicate_event_occurrences"] += 1
        else:
            events[key] = event
    region_history = {region: group for region, group in daily.groupby("region_code")}
    rows: list[dict[str, Any]] = []
    for event in events.values():
        try:
            start, end = _date(event["start_date"]), _date(event["end_date"])
        except (TypeError, ValueError):
            excluded["invalid_dates"] += 1
            continue
        duration = (end - start).days + 1
        if not 1 <= duration <= MAX_DURATION_DAYS:
            excluded["unsupported_duration"] += 1
            continue
        region = str(event["region_code"])
        if region not in region_history:
            excluded["missing_region_history"] += 1
            continue
        history = region_history[region]
        try:
            features = make_features(start, end, region, history)
        except InsufficientHistoryError:
            excluded["incomplete_feature_history"] += 1
            continue
        values = history.set_index("date")["visitor_count"]
        prior = values.reindex(pd.date_range(end=start - pd.Timedelta(days=1), periods=28))
        target = values.reindex(pd.date_range(start, end))
        if prior.isna().any() or target.isna().any():
            excluded["incomplete_label_window"] += 1
            continue
        baseline = float(prior.median())
        if baseline <= 0:
            excluded["nonpositive_label_baseline"] += 1
            continue
        level = float(target.mean())
        rows.append({
            "event_id": event["event_id"],
            "group_id": f"{region}:{start.date().isoformat()}:{end.date().isoformat()}",
            "start_date": start, "end_date": end, "region_code": region,
            "prediction_as_of": start - pd.Timedelta(days=LEAD_DAYS),
            "history_cutoff": start - pd.Timedelta(days=LEAD_DAYS + PUBLICATION_LAG_DAYS),
            "label_available_date": end + pd.Timedelta(days=PUBLICATION_LAG_DAYS),
            "uplift_rate": level / baseline - 1,
            "baseline_prior_28d_median": baseline, "event_window_daily_mean": level,
            **features,
        })
    if not rows:
        raise ValueError("엄격한 이력·정답 조건을 만족하는 행사 표본이 없습니다.")
    frame = pd.DataFrame(rows).sort_values(["start_date", "event_id"])
    identical_windows = int(frame["group_id"].duplicated().sum())
    source_ids = frame.groupby("group_id")["event_id"].agg(lambda values: json.dumps(sorted(set(values))))
    frame["source_event_ids"] = frame["group_id"].map(source_ids)
    frame = frame.drop_duplicates("group_id").reset_index(drop=True)
    audit = {
        "feature_version": FEATURE_VERSION, "visitor_data": visitor_audit,
        "festival_raw_rows": len(raw), "festival_normalized_rows": len(normalized),
        "festival_invalid_rows": len(raw) - len(normalized),
        "excluded": dict(excluded), "training_rows": len(frame),
        "identical_region_windows_removed": identical_windows,
        "regions": int(frame["region_code"].nunique()),
        "years": sorted(frame["start_date"].dt.year.unique().astype(int).tolist()),
        "start_date_min": frame["start_date"].min().date().isoformat(),
        "end_date_max": frame["end_date"].max().date().isoformat(),
        "festival_retrieved_at_min": min(retrieved), "festival_retrieved_at_max": max(retrieved),
        "assumed_lead_days": LEAD_DAYS, "assumed_publication_lag_days": PUBLICATION_LAG_DAYS,
        "history_days": HISTORY_DAYS, "max_duration_days": MAX_DURATION_DAYS,
        "historical_snapshot_verified": False,
        "limitations": [
            "지역 방문수요 증감률이며 특정 축제 관람객이나 인과적 행사 효과가 아닙니다.",
            "30일 사전 기획과 30일 공표 지연을 가정한 사후 재구성 평가입니다.",
            "당시 TourAPI 일정과 방문자 통계의 공개·수정 이력은 확보하지 못했습니다.",
            "같은 지역·동시 행사와 계절 변화의 영향을 포함합니다.",
        ],
    }
    return frame, daily, audit


def save_daily_history(daily: pd.DataFrame, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    daily.loc[:, DAILY_COLUMNS].to_csv(path, index=False, date_format="%Y-%m-%d")


def load_daily_history(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype={"region_code": str})
    if not set(DAILY_COLUMNS).issubset(frame.columns):
        raise ValueError("일별 방문자 이력 파일에 필수 열이 없습니다.")
    frame["date"] = frame["date"].map(_date)
    frame["visitor_count"] = pd.to_numeric(frame["visitor_count"], errors="raise")
    if (
        frame.empty or frame.duplicated(["date", "region_code"]).any()
        or not np.isfinite(frame["visitor_count"]).all()
        or (frame["visitor_count"] < 0).any()
        or not frame["region_code"].str.fullmatch(r"[0-9]{5}").all()
        or frame["region_code"].str.endswith("000").any()
        or pd.to_datetime(frame["retrieved_at"], utc=True, errors="coerce").isna().any()
    ):
        raise ValueError("일별 방문자 이력 파일이 품질 검증을 통과하지 못했습니다.")
    return frame.loc[:, DAILY_COLUMNS].sort_values(["date", "region_code"]).reset_index(drop=True)
