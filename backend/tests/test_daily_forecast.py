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
