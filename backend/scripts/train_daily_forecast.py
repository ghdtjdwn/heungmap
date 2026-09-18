"""지역 일별 D-30 방문수요 예측 모델 학습."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.demand.daily_training import train_daily_model
from app.demand.training_inputs import default_festival_paths, default_visitor_paths


def main() -> int:
    parser = argparse.ArgumentParser(description="D-30 시군구 일별 방문수요 모델 학습·평가")
    parser.add_argument("--visitors", type=Path, nargs="+", default=None, help="기본은 training_inputs.default_visitor_paths()")
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/daily-forecast-release"))
    parser.add_argument("--validation-start", default=None, help="기본은 default_split_dates(data_end)")
    parser.add_argument("--test-start", default=None)
    parser.add_argument("--festivals", type=Path, nargs="*", default=None,
                        help="TourAPI searchFestival2 JSONL. 인자만 주면 training_inputs 기본 3개 파일(v1.1 실험)")
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error("기존 실행 결과를 보존합니다. 새 --output-dir 경로를 지정하세요.")
    festivals = None if args.festivals is None else (args.festivals or default_festival_paths())
    summary = train_daily_model(args.visitors or default_visitor_paths(), args.output_dir,
                                validation_start=args.validation_start, test_start=args.test_start, festival_paths=festivals)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["model_adopted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
