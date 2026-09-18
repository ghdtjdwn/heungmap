"""문체부 연도별 지역축제 ZIP에서 축제별 전년도 보고 방문객 조회표를 만든다(Git 제외 경로)."""
from __future__ import annotations

import argparse
from pathlib import Path

from app.attendance.lookup import DEFAULT_PATH, build_lookup, summary_json, write_lookup


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archives", type=Path, nargs="+", default=sorted(Path("data/raw/mcst-festivals").glob("*_festival.zip")))
    parser.add_argument("--output", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args()
    table, audit = build_lookup(args.archives)
    write_lookup(table, args.output)
    print(summary_json(table, audit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
