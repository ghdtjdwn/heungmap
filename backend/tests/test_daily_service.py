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
    assert daily_service.prediction_regions(NOW) == [REGION]


def test_daily_artifact_corruption_and_unsupported_event_fail_closed(artifact):
    with (artifact / "p50.txt").open("a") as handle:
        handle.write("corrupt")
    assert predict().reason_code == "model_unavailable"
    assert daily_service.predict_demand(event_id="evt_planner_daily_test", start_date=date(2026, 10, 10),
        end_date=date(2026, 10, 12), region=REGION, event_type="concert", as_of=NOW).reason_code == "unsupported_event_type"


def test_model_status_reports_ready_stale_and_unavailable_without_paths(artifact, tmp_path, monkeypatch):
    ready = daily_service.model_status(NOW)
    assert ready["status"] == "ready" and ready["adopted"] and ready["regions"] == 1
    assert ready["last_predictable_target_date"] == date(2026, 10, 14) and ready["days_until_stale"] == 29
    stale = daily_service.model_status(datetime(2026, 11, 1, tzinfo=ZoneInfo("Asia/Seoul")))
    assert stale["status"] == "stale" and stale["days_until_stale"] < 0
    empty = tmp_path / "missing-model"
    monkeypatch.setenv("HEUNGMAP_DAILY_MODEL_DIR", str(empty))
    missing = daily_service.model_status(NOW)
    assert missing["status"] == "unavailable" and not missing["adopted"] and str(tmp_path) not in missing["reason"]


def test_model_status_endpoint_is_in_contract_and_never_fails(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app

    monkeypatch.setenv("HEUNGMAP_DAILY_MODEL_DIR", str(tmp_path / "none"))
    response = TestClient(app).get("/api/v1/system/model-status")
    assert response.status_code == 200
    assert response.json()["status"] == "unavailable" and "reason" in response.json()


def test_predict_rows_matches_online_prediction(artifact):
    result = predict()
    manifest, models, histories = daily_service._artifact()
    from app.demand.forecasting import make_forecast_features
    inputs, baselines = zip(*(make_forecast_features(day, histories["11110"]) for day in pd.date_range("2026-10-10", "2026-10-12")))
    _, center, _, _ = daily_service.predict_rows(models, manifest, pd.DataFrame(list(inputs)), baselines)
    assert round(float(center.sum())) == result.primary_metric.p50


def test_select_production_directory_prefers_newest_adopted(tmp_path):
    import json

    def run(number, adopted):
        path = tmp_path / f"daily-forecast-production-v{number}"
        path.mkdir()
        for name in ("manifest.json", "evaluation.json"):
            (path / name).write_text(json.dumps({"model_adopted": adopted}))
        return path

    v3 = run(3, True)
    run(4, False)
    assert daily_service.select_production_directory(tmp_path) == v3
    v10 = run(10, True)
    assert daily_service.select_production_directory(tmp_path) == v10
    (v10 / "evaluation.json").write_text("{broken")
    assert daily_service.select_production_directory(tmp_path) == v3
    assert daily_service.select_production_directory(tmp_path / "none") is None


def test_region_confidence_uses_holdout_wape_thresholds_and_keeps_legacy_medium():
    thresholds = {"high_below": 0.05, "medium_below": 0.10, "min_holdout_days": 10}
    def manifest(wape, days):
        return {"confidence_thresholds": thresholds, "regions": [{"code": "11110", "holdout_wape": wape, "holdout_days": days}]}
    assert daily_service.region_confidence(manifest(0.049, 19), "11110") == ("high", {"wape": 0.049, "days": 19})
    assert daily_service.region_confidence(manifest(0.05, 19), "11110")[0] == "medium"
    assert daily_service.region_confidence(manifest(0.10, 19), "11110")[0] == "low"
    assert daily_service.region_confidence(manifest(0.01, 9), "11110") == ("low", None)
    assert daily_service.region_confidence(manifest(None, 0), "11110") == ("low", None)
    assert daily_service.region_confidence({"regions": []}, "11110") == ("medium", None)


def test_regional_demand_level_needs_a_year_of_history_and_legacy_stays_unknown():
    percentiles = {"medium": 50, "high": 75, "very_high": 90, "min_days": 300}
    dates = pd.date_range("2025-08-14", "2026-08-13")
    history = pd.DataFrame({"date": dates, "visitor_count": np.arange(len(dates), dtype=float)})
    manifest = {"demand_level_percentiles": percentiles}
    assert daily_service.regional_demand_level(manifest, history, date(2026, 8, 13), 400.0)[0] == "very_high"
    assert daily_service.regional_demand_level(manifest, history, date(2026, 8, 13), 300.0)[0] == "high"
    assert daily_service.regional_demand_level(manifest, history, date(2026, 8, 13), 200.0)[0] == "medium"
    assert daily_service.regional_demand_level(manifest, history, date(2026, 8, 13), 10.0)[0] == "low"
    assert daily_service.regional_demand_level(manifest, history.tail(299), date(2026, 8, 13), 10.0) == ("unknown", None)
    assert daily_service.regional_demand_level({}, history, date(2026, 8, 13), 10.0) == ("unknown", None)


def test_prediction_merges_same_label_factors_and_explains_demand_level(artifact):
    result = predict()
    labels = [factor.label for factor in result.factors]
    assert len(labels) == len(set(labels)) and all("기여했습니다" in factor.explanation for factor in result.factors)
    assert result.indicators.congestion_level in {"low", "medium", "high", "very_high"}
    assert result.indicators.ticket_demand_level == "unknown"
    assert any(item.evidence_id == "ev_daily_demand_level" for item in result.evidence)
    assert any("현장 혼잡이 아닙니다" in item for item in result.limitations)
    merged = daily_service.merged_factors([0.1, 0.2, -0.05], ["month_sin", "month_cos", "recent_trend"])
    assert merged[0][1] == "계절" and abs(merged[0][2] - 0.3) < 1e-12


def predict_range(start, end, as_of=NOW):
    return daily_service.predict_demand(event_id="evt_planner_daily_window", start_date=start, end_date=end,
                                        region=REGION, event_type="festival", as_of=as_of)


def test_ongoing_event_predicts_only_remaining_days(artifact):
    result = predict_range(date(2026, 9, 10), date(2026, 9, 20))
    assert result.status == "available"
    assert (result.target_start_date, result.target_end_date) == (date(2026, 9, 15), date(2026, 9, 20))
    assert any("2026-09-15~2026-09-20 구간만 예측" in item for item in result.limitations)
    assert result.components[0].scope_description.startswith("예측 구간")


def test_long_event_is_capped_at_thirty_days_and_last_predictable_date(artifact):
    long_event = predict_range(date(2026, 9, 16), date(2026, 12, 31))
    assert (long_event.target_start_date, long_event.target_end_date) == (date(2026, 9, 16), date(2026, 10, 14))
    early = predict_range(date(2026, 9, 1), date(2026, 12, 31), as_of=datetime(2026, 9, 5, 12, tzinfo=ZoneInfo("Asia/Seoul")))
    assert (early.target_start_date, early.target_end_date) == (date(2026, 9, 5), date(2026, 10, 4))


def test_full_window_keeps_event_period_and_prediction_id(artifact):
    result = predict()
    assert (result.target_start_date, result.target_end_date) == (date(2026, 10, 10), date(2026, 10, 12))
    assert not any("구간만 예측" in item for item in result.limitations)


def test_ended_far_future_and_unpredictable_windows_are_unavailable(artifact):
    assert predict_range(date(2026, 9, 1), date(2026, 9, 14)).message == "이미 끝난 행사는 예측하지 않습니다."
    assert predict_range(date(2026, 10, 16), date(2026, 10, 18)).reason_code == "insufficient_data"
    assert predict_range(date(2026, 10, 20), date(2026, 10, 21)).message == "행사 시작 30일 전부터 예측을 제공합니다."
