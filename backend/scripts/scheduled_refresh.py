"""정기 실행용(cron): 새 방문자 자료 수집 → 필요하면 전향 평가·재학습 → 상태 기록. 매일 실행해도 안전하다."""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from app.demand.refresh import append_log, exit_code, refresh_lock, run_scheduled_refresh
from app.demand.training_inputs import RAW_DIRECTORY


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIRECTORY)
    parser.add_argument("--output-root", type=Path, default=RAW_DIRECTORY.parent / "processed")
    parser.add_argument("--no-collect", action="store_true", help="수집 없이 판단·재학습만")
    parser.add_argument("--min-new-days", type=int, default=7)
    args = parser.parse_args()
    try:
        with refresh_lock(args.output_root):
            result = run_scheduled_refresh(raw_dir=args.raw_dir, output_root=args.output_root, today=date.today(),
                                           collect=not args.no_collect, min_new_days=args.min_new_days)
    except Exception as exc:  # cron 로그에 남기고 실패 코드로 끝낸다. 서비스는 이전 채택 모델을 계속 쓴다.
        result = {"error": type(exc).__name__, "message": str(exc)[:500]}
        append_log(args.output_root, result)
        print(json.dumps(result, ensure_ascii=False))
        return 1
    log = append_log(args.output_root, result)
    print(json.dumps({**result, "log": str(log)}, ensure_ascii=False, indent=2, default=str))
    return exit_code(result)


if __name__ == "__main__":
    raise SystemExit(main())
