import numpy as np
import pandas as pd

from app.demand import daily_service
from app.demand.forward_evaluation import evaluate_frozen, size_quintiles
from app.demand.training_inputs import default_visitor_paths
from test_daily_service import artifact  # noqa: F401


def extended_daily():
    dates = pd.date_range("2025-01-01", "2026-08-31")
    visitors = 100_000 + dates.dayofweek * 2_000 + np.sin(np.arange(len(dates)) / 15) * 3_000
    return pd.DataFrame({"date": dates, "region_code": "11110", "region_name": "합성 시군구",
                         "visitor_count": visitors, "retrieved_at": "2026-09-18T00:00:00+00:00"})


def test_frozen_evaluation_scores_only_new_days_without_touching_artifact(artifact):  # noqa: F811
    before = {path.name: path.stat().st_mtime_ns for path in artifact.iterdir()}
    manifest, models, _ = daily_service._artifact()
    report, frame = evaluate_frozen(manifest, models, extended_daily(), "2026-08-16")
    assert report["period"] == {"start": "2026-08-16", "end": "2026-08-31"} and report["rows"] == 16
    assert frame.date.min() == pd.Timestamp("2026-08-16") and report["skipped_rows"] == 0
    assert report["model"]["wape"] >= 0 and 0 <= report["interval_80_coverage"] <= 1
    assert {"seasonal_growth_baseline", "wape_improvement", "by_size_quintile", "worst_regions"} <= set(report)
    assert {path.name: path.stat().st_mtime_ns for path in artifact.iterdir()} == before


def test_size_quintiles_split_rows_evenly():
    frame = pd.DataFrame({"target": np.arange(1, 11, dtype=float), "p50": np.arange(1, 11, dtype=float) * 1.1})
    rows = size_quintiles(frame)
    assert [row["n"] for row in rows] == [2] * 5 and rows[0]["mean_actual"] < rows[-1]["mean_actual"]


def test_default_visitor_paths_append_refresh_files_in_collection_order(tmp_path):
    for name in ("visitors-2026-aug-sep-refresh-20260918.jsonl", "visitors-2026-aug-refresh-20260915.jsonl", "visitors.jsonl"):
        (tmp_path / name).write_text("")
    assert [path.name for path in default_visitor_paths(tmp_path)] == [
        "visitors-2025-full.jsonl", "visitors-2026-jan-aug.jsonl",
        "visitors-2026-aug-refresh-20260915.jsonl", "visitors-2026-aug-sep-refresh-20260918.jsonl"]
