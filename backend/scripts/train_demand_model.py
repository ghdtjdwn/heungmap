"""저장소 루트에서 실행: PYTHONPATH=backend .venv/bin/python backend/scripts/train_demand_model.py"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.demand.data import build_training_dataset
from app.demand.training import evaluate, save_run


def main():
    parser = argparse.ArgumentParser(description="지역 방문수요 모델의 수집자료 검증·학습·시간/지역 평가·저장")
    parser.add_argument("--festivals", type=Path, nargs="+", default=[Path("data/raw/festivals-2025.jsonl"), Path("data/raw/festivals-2026-jan-aug.jsonl")])
    parser.add_argument("--visitors", type=Path, nargs="+", default=[Path("data/raw/visitors-2025-full.jsonl"), Path("data/raw/visitors-2026-jan-aug.jsonl")])
    parser.add_argument("--test-start", default="2026-07-01")
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/demand-model-release"))
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error("기존 실행 결과를 보존합니다. 새 --output-dir 경로를 지정하세요.")
    frame, daily, audit = build_training_dataset(args.festivals, args.visitors)
    print(json.dumps({"training_rows": len(frame), "daily_rows": len(daily), "audit": audit}, ensure_ascii=False), flush=True)
    report, models, predictions = evaluate(frame, test_start=args.test_start)
    save_run(args.output_dir, report, models, predictions, frame, daily, audit, [*args.festivals, *args.visitors])
    print(json.dumps({"output": str(args.output_dir), "model_adopted": report["model_adopted"],
                      "holdout": report["time_holdout"]["model"], "checks": report["adoption_checks"]}, ensure_ascii=False, indent=2))
    return 0 if report["model_adopted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
