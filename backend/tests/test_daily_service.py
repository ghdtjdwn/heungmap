from datetime import date, datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from app.demand import daily_service
from app.demand.forecasting import CANDIDATES, _fit, build_daily_forecast_dataset, save_daily_run
from app.schemas import RegionRef


NOW = datetime(2026, 9, 15, 12, tzinfo=ZoneInfo("Asia/Seoul"))
REGION = RegionRef(area_code="1", legal_dong_code="11110", display_name="합성 시군구")


@pytest.fixture
def artifact(tmp_path, monkeypatch):
    dates = pd.date_range("2025-01-01", "2026-08-15")
    visitors = 100_000 + dates.dayofweek * 2_000 + np.sin(np.arange(len(dates)) / 15) * 3_000
    daily = pd.DataFrame({"date": dates, "region_code": "11110", "region_name": "합성 시군구",
                          "visitor_count": visitors, "retrieved_at": "2026-09-01T00:00:00+00:00"})
    frame, _ = build_daily_forecast_dataset(daily)
    parameters = CANDIDATES[0]
    models = tuple(_fit(frame, parameters, alpha) for alpha in (0.1, None, 0.9))
    report = {"generated_at": "2026-09-02T00:00:00+00:00", "model_version": "synthetic-daily",
              "model_adopted": True, "adoption_checks": {"fixture": True},
              "selected_candidate": {"parameters": parameters},
              "calibration_log_error_quantiles": [-0.1, 0.1], "limitations": ["합성 테스트 자료"]}
    output = tmp_path / "daily-artifact"
    save_daily_run(output, report, models, frame.tail(2), frame, daily, {}, [])
    monkeypatch.setenv("HEUNGMAP_DAILY_MODEL_DIR", str(output))
    daily_service._load.cache_clear()
    yield output
    daily_service._load.cache_clear()


def predict():
    return daily_service.predict_demand(event_id="evt_planner_daily_test", start_date=date(2026, 10, 10),
                                        end_date=date(2026, 10, 12), region=REGION,
                                        event_type="festival", as_of=NOW)


def test_daily_artifact_serves_people_range_and_is_deterministic(artifact):
    result = predict()
    assert result.status == "available" and result.primary_metric.unit == "people"
    assert result.primary_metric.p10 <= result.primary_metric.p50 <= result.primary_metric.p90
    assert result.components[0].unit == "people" and result.data_sufficiency == "sufficient"
    assert {source.source_type for source in result.sources} == {"heungmap_model", "kto_datalab"}
    assert result.prediction_id == predict().prediction_id
    assert daily_service.prediction_regions() == [REGION]


def test_daily_artifact_corruption_and_unsupported_event_fail_closed(artifact):
    with (artifact / "p50.txt").open("a") as handle:
        handle.write("corrupt")
    assert predict().reason_code == "model_unavailable"
    assert daily_service.predict_demand(event_id="evt_planner_daily_test", start_date=date(2026, 10, 10),
        end_date=date(2026, 10, 12), region=REGION, event_type="concert", as_of=NOW).reason_code == "unsupported_event_type"
