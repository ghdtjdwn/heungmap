"""문체부 축제별 방문객 실적 모델을 학습하고 독립 미래연도로 평가한다."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.attendance.data import build_training_pairs, load_archives
from app.attendance.training import evaluate, save_run


def main() -> int:
    parser = argparse.ArgumentParser(description="문체부 반복 축제 관람수요 모델 학습·평가")
    parser.add_argument("--archives", type=Path, nargs="+", default=sorted(Path("data/raw/mcst-festivals").glob("*_festival.zip")))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/attendance-model-release"))
    parser.add_argument("--validation-year", type=int, default=2024)
    parser.add_argument("--test-year", type=int, default=2025)
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error("기존 실행 결과를 보존합니다. 새 --output-dir 경로를 지정하세요.")
    records, source_audit = load_archives(args.archives)
    frame, pair_audit = build_training_pairs(records)
    report, models, predictions = evaluate(frame, validation_year=args.validation_year, test_year=args.test_year)
    audit = {"source": source_audit, "pairs": pair_audit}
    save_run(args.output_dir, report, models, predictions, frame, records, audit, list(args.archives))
    print(json.dumps({"output": str(args.output_dir), "model_adopted": report["model_adopted"],
                      "holdout": report["time_holdout"], "subsets": report["measurement_subsets"],
                      "checks": report["adoption_checks"]}, ensure_ascii=False, indent=2))
    return 0 if report["model_adopted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

