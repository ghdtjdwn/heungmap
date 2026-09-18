"""새 방문자 자료를 append-only로 수집하고 다음 production-v* 폴더에 재학습한다. 서비스 설정은 바꾸지 않는다."""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date, timedelta
from pathlib import Path

from app.data_gate.cli import collect
from app.demand.daily_training import next_production_directory, train_daily_model
from app.demand.training_inputs import RAW_DIRECTORY, default_visitor_paths, latest_raw_date


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=Path("data/processed"))
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIRECTORY)
    parser.add_argument("--no-collect", action="store_true", help="수집 없이 이미 받은 원본으로만 재학습")
    args = parser.parse_args()
    if not args.no_collect:
        # 이미 받은 마지막 날 다음부터만 받는다. 겹쳐 받으면 수정된 값이 기존 값과 충돌해 학습이 중단된다.
        start = latest_raw_date(default_visitor_paths(args.raw_dir)) + timedelta(days=1)
        today = date.today()
        output = args.raw_dir / f"visitors-{start:%Y%m}-{today:%Y%m}-refresh-{today:%Y%m%d}.jsonl"
        if start > today:
            print(json.dumps({"status": "no_new_data", "requested_from": start.isoformat()}, ensure_ascii=False))
            return 3
        asyncio.run(collect("visitors", f"{start:%Y%m%d}", f"{today:%Y%m%d}", output, max_pages=20, rows=10000))
        if not output.exists() or latest_raw_date([output]) < start:
            output.unlink(missing_ok=True)  # 빈 응답 페이지만 담긴 이번 실행 파일은 남기지 않는다.
            print(json.dumps({"status": "no_new_data", "requested_from": start.isoformat()}, ensure_ascii=False))
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
