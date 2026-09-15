"""저장 모델의 배치/온라인 일치·설명 합산·원본 checksum 검증. 외부 API를 호출하지 않는다."""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from time import perf_counter
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from app.demand import service
from app.demand.data import FEATURES
from app.demand.training import file_digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=service.DEFAULT_DIRECTORY)
    parser.add_argument("--source-dir", type=Path, default=Path("data/raw"))
    args = parser.parse_args()
    os.environ["HEUNGMAP_DEMAND_MODEL_DIR"] = str(args.model_dir.resolve())
    started = perf_counter()
    manifest, models, _ = service._artifact()
    load_seconds = perf_counter() - started
    for source in manifest["source_files"]:
        if file_digest(args.source_dir / source["name"]) != source["sha256"]:
            raise ValueError("학습에 사용한 원본 checksum이 일치하지 않습니다.")
    training = pd.read_csv(args.model_dir / "training.csv", dtype={"region_code": str, "event_id": str})
    holdout = pd.read_csv(args.model_dir / "holdout-predictions.csv", dtype={"region_code": str, "event_id": str})
    frame = training.set_index("group_id").loc[holdout.group_id].reset_index()
    spec = manifest["parameters"]
    weight = spec["model_weight"]
    baseline = frame.calendar_expected_uplift.to_numpy() * (1 if spec["residual"] else 1 - weight)
    center = np.maximum(-1, baseline + weight * models[1].predict(frame[FEATURES], num_threads=1))
    np.testing.assert_allclose(center, holdout.p50.to_numpy(), atol=1e-10, rtol=0)
    contributions = models[1].predict(frame[FEATURES], pred_contrib=True, num_threads=1)
    np.testing.assert_allclose(np.maximum(-1, baseline + weight * contributions.sum(axis=1)), center, atol=1e-10, rtol=0)
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    regions = service.prediction_regions()
    results = []
    started = perf_counter()
    for region in regions:
        result = service.predict_demand(event_id="evt_planner_local_verification", start_date=now.date() + timedelta(days=7),
                                        end_date=now.date() + timedelta(days=9), region=region, event_type="festival", as_of=now)
        results.append(result)
    elapsed = perf_counter() - started
    available = sum(result.status == "available" for result in results)
    if not available:
        raise ValueError("현재 일정에 온라인 예측 가능한 시군구가 없습니다. 자료를 갱신하세요.")
    print(json.dumps({
        "model_version": manifest["model_version"], "model_adopted": manifest["model_adopted"],
        "source_checksums_verified": len(manifest["source_files"]),
        "holdout_prediction_roundtrip_rows": len(holdout), "shap_additivity_verified": True,
        "catalog_regions": len(regions), "online_available_regions": available,
        "online_unavailable_regions": len(results) - available, "model_load_seconds": round(load_seconds, 3),
        "mean_online_seconds": round(elapsed / len(results), 4),
        "is_mock": False,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
