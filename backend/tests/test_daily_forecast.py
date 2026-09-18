import numpy as np
import pandas as pd

from app.demand.forecasting import FEATURES, build_daily_forecast_dataset, make_forecast_features, metrics


def test_daily_features_use_only_history_through_target_minus_60_days():
    dates = pd.date_range("2025-01-01", "2026-08-15")
    values = 1000 + dates.dayofweek * 10 + np.sin(np.arange(len(dates)) / 15) * 20
    daily = pd.DataFrame({"date": dates, "region_code": "11110", "region_name": "합성지역",
                          "visitor_count": values, "retrieved_at": "2026-09-15T00:00:00+00:00"})
    frame, audit = build_daily_forecast_dataset(daily)
    assert list(frame[FEATURES].columns) == FEATURES
    assert (frame.date - frame.history_cutoff).dt.days.eq(60).all()
    assert audit["regions"] == 1 and np.isfinite(frame[FEATURES]).all().all()
    row = frame.iloc[-1]
    inputs, baseline = make_forecast_features(row.date, daily)
    np.testing.assert_allclose([inputs[name] for name in FEATURES], row[FEATURES].to_numpy(dtype=float))
    assert baseline == row.baseline


def test_daily_metrics_are_exact_for_perfect_prediction():
    result = metrics([10, 20], [10, 20])
    assert result["wape"] == result["rmsle"] == 0
    assert result["within_20_percent"] == 1


def test_default_split_dates_follow_v3_rule():
    from app.demand.forecasting import default_split_dates

    assert default_split_dates("2026-08-15") == ("2026-07-01", "2026-08-01")  # v3 실제 분할
    assert default_split_dates("2026-08-19") == ("2026-07-01", "2026-08-01")
    assert default_split_dates("2026-09-10") == ("2026-07-01", "2026-08-01")  # 9월 관측 15일 미만
    assert default_split_dates("2026-09-20") == ("2026-08-01", "2026-09-01")
    assert default_split_dates("2027-01-03") == ("2026-11-01", "2026-12-01")


def test_next_production_directory_increments_and_never_reuses(tmp_path):
    import pytest
    from app.demand.daily_training import next_production_directory

    assert next_production_directory(tmp_path).name == "daily-forecast-production-v1"
    for name in ("daily-forecast-production-v3", "daily-forecast-production", "daily-forecast-production-v10-copy"):
        (tmp_path / name).mkdir()
    assert next_production_directory(tmp_path).name == "daily-forecast-production-v4"
    with pytest.raises(FileNotFoundError):
        from app.demand.daily_training import train_daily_model
        train_daily_model([tmp_path / "missing.jsonl"], tmp_path / "new-run")


def test_latest_raw_date_reads_page_items(tmp_path):
    import json
    from datetime import date
    from app.demand.training_inputs import latest_raw_date

    path = tmp_path / "visitors-refresh.jsonl"
    path.write_text("\n".join(json.dumps({"items": items}) for items in (
        [{"baseYmd": "20260816"}], [{"baseYmd": "20260819"}, {"baseYmd": "20260817"}], [])) + "\n")
    assert latest_raw_date([path, tmp_path / "missing.jsonl"]) == date(2026, 8, 19)
    assert latest_raw_date([tmp_path / "missing.jsonl"]) == date.min
