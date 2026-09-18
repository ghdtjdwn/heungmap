"""채택 일별 모델의 상태·원본 checksum·홀드아웃 재계산·온라인 예측을 점검한다. 외부 API를 호출하지 않는다."""
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

from app.demand import daily_service
from app.demand.forecasting import file_digest, make_forecast_features


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=None, help="기본은 서비스가 자동 선택하는 artifact")
    parser.add_argument("--source-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--roundtrip-rows", type=int, default=300, help="홀드아웃 재계산 표본 행 수(0이면 전체)")
    args = parser.parse_args()
    if args.model_dir:
        os.environ["HEUNGMAP_DAILY_MODEL_DIR"] = str(args.model_dir.resolve())
    directory = daily_service._directory()
    status = daily_service.model_status()
    if status["status"] == "unavailable":
        print(json.dumps({"model_dir": str(directory), **status}, ensure_ascii=False, default=str, indent=2))
        return 1
    manifest, models, histories = daily_service._artifact()
    for source in manifest["source_files"]:
        if file_digest(args.source_dir / source["name"]) != source["sha256"]:
            raise ValueError(f"학습 원본 checksum 불일치: {source['name']}")
    holdout = pd.read_csv(directory / "holdout-predictions.csv", dtype={"region_code": str}, parse_dates=["date"])
    if args.roundtrip_rows:
        holdout = holdout.sample(min(args.roundtrip_rows, len(holdout)), random_state=0)
    inputs, baselines = [], []
    for row in holdout.itertuples():
        values, baseline = make_forecast_features(row.date, histories[row.region_code])
        inputs.append(values)
        baselines.append(baseline)
    _, center, _, _ = daily_service.predict_rows(models, manifest, pd.DataFrame(inputs), baselines)
    np.testing.assert_allclose(baselines, holdout.baseline.to_numpy(), rtol=1e-9)
    np.testing.assert_allclose(center, holdout.p50.to_numpy(), rtol=1e-6)
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    regions = daily_service.prediction_regions()
    started = perf_counter()
    results = [daily_service.predict_demand(event_id="evt_planner_local_verification", start_date=now.date() + timedelta(days=7),
                                            end_date=now.date() + timedelta(days=9), region=region, event_type="festival", as_of=now)
               for region in regions]
    elapsed = perf_counter() - started
    available = sum(result.status == "available" for result in results)
    print(json.dumps({
        "model_dir": str(directory), **status, "source_checksums_verified": len(manifest["source_files"]),
        "holdout_roundtrip_rows": len(holdout), "catalog_regions": len(regions), "online_available_regions": available,
        "online_unavailable_regions": len(results) - available,
        "mean_online_seconds": round(elapsed / max(1, len(results)), 4),
    }, ensure_ascii=False, default=str, indent=2))
    return 0 if status["status"] == "ready" and available else 1


if __name__ == "__main__":
    raise SystemExit(main())
