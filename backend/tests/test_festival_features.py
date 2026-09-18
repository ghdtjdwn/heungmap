import numpy as np
import pandas as pd

from app.demand.daily_training import add_festival_ablation
from app.demand.festivals import FESTIVAL_FEATURES, calendar_from_items, festival_features
from app.demand.forecasting import FEATURES, build_daily_forecast_dataset, make_forecast_features


def item(content_id, start, end, created, legal=("11", "110")):
    return {"contentid": content_id, "title": f"축제{content_id}", "eventstartdate": start, "eventenddate": end,
            "createdtime": created + "090000", "lDongRegnCd": legal[0], "lDongSignguCd": legal[1]}


CALENDAR = calendar_from_items([
    item("1", "20260810", "20260812", "20260601"),   # D-30 이전 등록
    item("2", "20260811", "20260811", "20260801"),   # 목표일 10일 전 등록 → 누수라 제외
    item("3", "20260815", "20260815", "20250101"),   # 창(±3일) 밖
    item("4", "20260811", "20260811", "20260101", legal=("26", "110")),  # 다른 시군구
    {"contentid": "5", "title": "등록일 없음", "eventstartdate": "20260811", "eventenddate": "20260811", "lDongRegnCd": "11", "lDongSignguCd": "110"},
])


def test_calendar_keeps_only_dated_sigungu_rows():
    assert list(CALENDAR.event_id) == ["1", "2", "3", "4"] and set(CALENDAR.region_code) == {"11110", "26110"}


def test_festival_features_ignore_festivals_registered_after_d30():
    values = festival_features("2026-08-11", "11110", CALENDAR)
    assert values == {"festival_active": 1.0, "festival_days_in_window": 3.0}
    assert festival_features("2026-08-11", "11140", CALENDAR) == dict.fromkeys(FESTIVAL_FEATURES, 0.0)


def test_calendar_is_optional_and_extends_training_rows_consistently():
    dates = pd.date_range("2025-01-01", "2026-08-15")
    daily = pd.DataFrame({"date": dates, "region_code": "11110", "region_name": "합성지역",
                          "visitor_count": 1000 + dates.dayofweek * 10.0, "retrieved_at": "2026-09-15T00:00:00+00:00"})
    plain, _ = build_daily_forecast_dataset(daily)
    extended, _ = build_daily_forecast_dataset(daily, CALENDAR)
    np.testing.assert_allclose(plain[FEATURES].to_numpy(), extended[FEATURES].to_numpy())
    row = extended.loc[extended.date == "2026-08-11"].iloc[0]
    assert row.festival_active == 1 and row.festival_days_in_window == 3
    inputs, _ = make_forecast_features("2026-08-11", daily, CALENDAR)
    assert list(inputs) == FEATURES + FESTIVAL_FEATURES and inputs["festival_active"] == 1
    assert list(make_forecast_features("2026-08-11", daily)[0]) == FEATURES


def test_festival_model_must_beat_same_rows_without_festivals():
    def report(wape):
        return {"selected_candidate": {"metrics": {"wape": wape}, "parameters": {}}, "time_holdout": {"model": {"wape": wape}},
                "adoption_checks": {"base": True}}
    assert add_festival_ablation(report(0.04), report(0.05))["model_adopted"] is True
    rejected = add_festival_ablation(report(0.05), report(0.05))
    assert rejected["model_adopted"] is False and rejected["rejection_reasons"] == ["beats_no_festival_validation_wape"]
