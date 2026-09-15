"""지역 일별 D-30 방문수요 예측 모델 학습."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.demand.data import load_daily_visitors
from app.demand.forecasting import build_daily_forecast_dataset, evaluate_daily_forecast, save_daily_run


def main() -> int:
    parser = argparse.ArgumentParser(description="D-30 시군구 일별 방문수요 모델 학습·평가")
    parser.add_argument("--visitors", type=Path, nargs="+", default=[
        Path("data/raw/visitors-2025-full.jsonl"), Path("data/raw/visitors-2026-jan-aug.jsonl"),
        Path("data/raw/visitors-2026-aug-refresh-20260915.jsonl")])
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/daily-forecast-release"))
    parser.add_argument("--validation-start", default="2026-07-01")
    parser.add_argument("--test-start", default="2026-08-01")
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error("기존 실행 결과를 보존합니다. 새 --output-dir 경로를 지정하세요.")
    daily, source_audit = load_daily_visitors(args.visitors)
    frame, feature_audit = build_daily_forecast_dataset(daily)
    report, models, predictions = evaluate_daily_forecast(
        frame, validation_start=args.validation_start, test_start=args.test_start)
    save_daily_run(args.output_dir, report, models, predictions, frame, daily,
                   {"source": source_audit, "features": feature_audit}, args.visitors)
    print(json.dumps({"output": str(args.output_dir), "model_adopted": report["model_adopted"],
                      "holdout": report["time_holdout"], "checks": report["adoption_checks"]}, ensure_ascii=False, indent=2))
    return 0 if report["model_adopted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
