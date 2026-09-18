"""새 방문자 자료를 append-only로 수집하고 다음 production-v* 폴더에 재학습한다. 서비스 설정은 바꾸지 않는다."""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from app.demand.daily_training import next_production_directory, train_daily_model
from app.demand.refresh import collect_new_visitors
from app.demand.training_inputs import RAW_DIRECTORY, default_visitor_paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=Path("data/processed"))
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIRECTORY)
    parser.add_argument("--no-collect", action="store_true", help="수집 없이 이미 받은 원본으로만 재학습")
    args = parser.parse_args()
    if not args.no_collect:
        collected = collect_new_visitors(args.raw_dir, date.today())
        if collected["status"] == "no_new_data":
            print(json.dumps(collected, ensure_ascii=False))
            return 3
    visitors = default_visitor_paths(args.raw_dir)
    output_dir = next_production_directory(args.output_root)
    summary = train_daily_model(visitors, output_dir)
    summary["next_step"] = ("자동 선택이 이 폴더를 사용합니다. 고정하려면 HEUNGMAP_DAILY_MODEL_DIR=" + str(output_dir.resolve())
                            if summary["model_adopted"] else "미채택: 서비스는 이전 채택 폴더를 계속 사용합니다.")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["model_adopted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
