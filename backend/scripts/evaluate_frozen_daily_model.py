"""채택된 일별 모델을 학습에 쓰지 않은 새 관측일에 그대로 채점한다. 모델·manifest를 수정하지 않는다."""
from __future__ import annotations

import argparse
import json
import os
from datetime import date, timedelta
from pathlib import Path

from app.demand import daily_service
from app.demand.data import load_daily_visitors
from app.demand.forward_evaluation import evaluate_frozen
from app.demand.training_inputs import default_visitor_paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=daily_service.DEFAULT_DIRECTORY)
    parser.add_argument("--visitors", type=Path, nargs="+", default=None)
    parser.add_argument("--start", default=None, help="YYYY-MM-DD, 기본은 모델 data_end 다음 날")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    os.environ["HEUNGMAP_DAILY_MODEL_DIR"] = str(args.model_dir.resolve())
    manifest, models, _ = daily_service._artifact()
    start = args.start or (date.fromisoformat(manifest["data_end"]) + timedelta(days=1)).isoformat()
    output = args.output or args.model_dir / f"forward-evaluation-{date.today():%Y%m%d}.json"
    if output.exists():
        parser.error("기존 전향 평가 결과를 보존합니다. 새 --output 경로를 지정하세요.")
    daily, _ = load_daily_visitors(args.visitors or default_visitor_paths())
    report, _ = evaluate_frozen(manifest, models, daily, start)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), **report}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
