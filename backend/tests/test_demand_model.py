from datetime import date, datetime, timedelta, timezone
import json

import pytest

np = pytest.importorskip("numpy")
pd = pytest.importorskip("pandas")
pytest.importorskip("lightgbm")

from app.demand.data import FEATURES, make_features
from app.demand import service
from app.demand.training import fit_model, predict_model, save_run, temporal_split, uncertainty
from app.schemas import RegionRef

NOW = datetime(2026, 9, 15, 12, tzinfo=timezone.utc)
REGION = RegionRef(area_code="1", legal_dong_code="11110", display_name="합성 시군구")
SPEC = {"objective": "regression_l1", "num_leaves": 3, "n_estimators": 15,
        "min_child_samples": 3, "residual": False, "model_weight": .5}


@pytest.fixture
def artifact(tmp_path, monkeypatch):
    dates = pd.date_range("2025-01-01", "2026-08-20")
    daily = pd.DataFrame({"date": dates, "region_code": "11110", "region_name": "합성 시군구",
                          "visitor_count": 100 + (dates.dayofweek >= 5) * 30 + np.sin(np.arange(len(dates)) / 8) * 5,
                          "retrieved_at": "2026-09-01T00:00:00+00:00"})
    rows = []
    for i, start in enumerate(pd.date_range("2025-06-01", periods=100, freq="3D")):
        end = start + timedelta(days=i % 7)
        features = make_features(start, end, "11110", daily)
        rows.append({"region_code": "11110", "uplift_rate": features["calendar_expected_uplift"] * .8 + .01,
                     **features})
    frame = pd.DataFrame(rows)
    models = [fit_model(frame, SPEC, alpha=.1), fit_model(frame, SPEC), fit_model(frame, SPEC, alpha=.9)]
    report = {"generated_at": "2026-09-02T00:00:00+00:00", "model_version": "synthetic-test",
              "model_adopted": True, "features": FEATURES, "adoption_checks": {"synthetic_fixture": True},
              "selected_candidate": {"parameters": SPEC, "residual_quantiles": [-.08, .12]},
              "split": {"train_last_event_end": "2026-05-02"}, "limitations": ["테스트용 합성 자료"],
              "training_scope": {"regions": ["11110"], "feature_ranges": {name: [float(frame[name].min()), float(frame[name].max())] for name in FEATURES}}}
    directory = tmp_path / "artifact"
    save_run(directory, report, models, frame, frame, daily, {"festival_retrieved_at_max": "2026-09-01T00:00:00+00:00"}, [])
    monkeypatch.setenv("HEUNGMAP_DEMAND_MODEL_DIR", str(directory))
    service._load.cache_clear()
    yield directory, models, daily, frame
    service._load.cache_clear()


def predict(**overrides):
    arguments = {"event_id": "evt_planner_test", "start_date": date(2026, 9, 20),
                 "end_date": date(2026, 9, 22), "region": REGION, "event_type": "festival", "as_of": NOW}
    return service.predict_demand(**(arguments | overrides))


def test_temporal_split_purges_late_labels_and_overlapping_windows():
    frame = pd.DataFrame({
        "start_date": pd.to_datetime(["2026-04-01", "2026-04-01", "2026-02-01", "2026-07-01"]),
        "label_available_date": pd.to_datetime(["2026-06-01", "2026-06-02", "2026-07-20", "2026-08-02"]),
        "group_id": ["ok", "late", "long", "future"],
    })
    train, test = temporal_split(frame, "2026-07-01")
    assert train.group_id.tolist() == ["ok"]
    assert test.group_id.tolist() == ["future"]


def test_saved_model_and_service_match_batch_prediction_and_units(artifact):
    _, models, daily, _ = artifact
    features = pd.DataFrame([make_features(date(2026, 9, 20), date(2026, 9, 22), "11110", daily)])
    expected = uncertainty(models, features, SPEC, [-.08, .12])[0] * 100
    result = predict()
    assert result.status == "available"
    assert result.is_mock is False and result.method == "machine_learning"
    assert result.primary_metric.unit == "percent_change"
    np.testing.assert_allclose([result.primary_metric.p10, result.primary_metric.p50, result.primary_metric.p90], expected, atol=.00051)
    assert result.indicators.demand_score is None
    assert result.indicators.ticket_demand_level == "unknown"
    assert {source.source_type for source in result.sources} == {"tourapi", "kto_datalab", "heungmap_model"}
    assert result.prediction_id == predict().prediction_id
    assert service.prediction_regions()[0].legal_dong_code == "11110"


def test_native_contributions_and_deterministic_training(artifact):
    _, models, _, frame = artifact
    again = fit_model(frame, SPEC)
    np.testing.assert_array_equal(predict_model(again, frame, SPEC), predict_model(models[1], frame, SPEC))
    contributions = models[1].booster_.predict(frame[FEATURES], pred_contrib=True, num_threads=1)
    weighted_sum = contributions.sum(axis=1) * .5 + frame.calendar_expected_uplift.to_numpy() * .5
    np.testing.assert_allclose(weighted_sum, predict_model(models[1], frame, SPEC), atol=1e-10)


def test_missing_artifact_returns_explicit_unavailable(tmp_path, monkeypatch):
    monkeypatch.setenv("HEUNGMAP_DEMAND_MODEL_DIR", str(tmp_path / "missing"))
    result = predict()
    assert result.status == "unavailable" and result.reason_code == "model_unavailable"
    assert result.is_mock is False


def test_rejected_artifact_never_served(artifact):
    directory, *_ = artifact
    manifest = json.loads((directory / "manifest.json").read_text())
    manifest["model_adopted"] = False
    (directory / "manifest.json").write_text(json.dumps(manifest))
    assert predict().reason_code == "model_unavailable"
    assert service.prediction_regions() == []


def test_cached_artifact_is_revalidated_after_corruption(artifact):
    directory, *_ = artifact
    assert predict().status == "available"
    with (directory / "p50.txt").open("a") as handle:
        handle.write("corrupted")
    assert predict().reason_code == "model_unavailable"


def test_json_array_manifest_is_unavailable_not_server_error(artifact):
    directory, *_ = artifact
    (directory / "manifest.json").write_text("[]")
    assert predict().reason_code == "model_unavailable"


@pytest.mark.parametrize("overrides,reason", [
    ({"event_type": "concert"}, "unsupported_event_type"),
    ({"region": RegionRef(area_code="1", display_name="지역 미정")}, "missing_required_input"),
    ({"region": RegionRef(area_code="6", legal_dong_code="11110", display_name="불일치")}, "missing_required_input"),
    ({"start_date": date(2026, 9, 14)}, "insufficient_data"),
    ({"start_date": date(2026, 10, 16), "end_date": date(2026, 10, 18)}, "insufficient_data"),
    ({"end_date": date(2026, 10, 25)}, "insufficient_data"),
    ({"region": RegionRef(area_code="1", legal_dong_code="11999", display_name="미지원")}, "insufficient_data"),
])
def test_unsupported_inputs_never_generate_fabricated_scores(artifact, overrides, reason):
    result = predict(**overrides)
    assert result.status == "unavailable" and result.reason_code == reason
    assert result.is_mock is False


def test_uncollected_history_and_future_model_are_not_available(artifact):
    assert predict(start_date=date(2026, 8, 10), end_date=date(2026, 8, 12),
                   as_of=datetime(2026, 8, 1, tzinfo=timezone.utc)).reason_code == "insufficient_data"


def test_runs_cannot_overwrite_existing_results(artifact):
    directory, models, daily, frame = artifact
    with pytest.raises(FileExistsError):
        save_run(directory, {}, models, frame, frame, daily, {}, [])


@pytest.mark.parametrize("missing", ["festival_retrieved_at", "created_at", "limitations", "training_scope", "model_version"])
def test_invalid_manifest_metadata_is_unavailable_not_server_error(artifact, missing):
    directory, *_ = artifact
    path = directory / "manifest.json"
    manifest = json.loads(path.read_text())
    del manifest[missing]
    path.write_text(json.dumps(manifest))
    assert predict().reason_code == "model_unavailable"


def test_same_instant_in_utc_and_korea_uses_same_calendar_date(artifact):
    from zoneinfo import ZoneInfo
    instant = datetime(2026, 9, 14, 16, tzinfo=timezone.utc)
    args = {"start_date": date(2026, 10, 15), "end_date": date(2026, 10, 15)}
    utc_result = predict(**args, as_of=instant)
    korean_result = predict(**args, as_of=instant.astimezone(ZoneInfo("Asia/Seoul")))
    assert utc_result.model_dump() == korean_result.model_dump()
    assert utc_result.status == "available"


def test_training_scope_detects_out_of_distribution_inputs(artifact):
    directory, *_ = artifact
    result = predict(end_date=date(2026, 10, 10))
    assert result.status == "available" and result.out_of_distribution
