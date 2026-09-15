"""문체부 연도별 지역축제 원본 수집. 저장소 루트에서 실행한다."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.attendance.data import DOWNLOAD_URL, SUPPORTED_YEARS


def main() -> int:
    parser = argparse.ArgumentParser(description="문체부 지역축제 연도별 ZIP 수집")
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw/mcst-festivals"))
    parser.add_argument("--years", type=int, nargs="+", default=list(SUPPORTED_YEARS))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for year in args.years:
        if year not in SUPPORTED_YEARS:
            parser.error(f"지원하지 않는 연도입니다: {year}")
        destination = args.output_dir / f"{year}_festival.zip"
        if destination.exists():
            parser.error(f"기존 원본을 덮어쓰지 않습니다: {destination}")
        query = urlencode({"pFileName": f"{year}_festival.zip", "pRealName": f"{year}_festival.zip",
                           "pPath": "PORTAL.DOCUMENT.UPLOAD", "pFlag": ""})
        request = Request(f"{DOWNLOAD_URL}?{query}", headers={"User-Agent": "HeungMap data collection/1.0"})
        with urlopen(request, timeout=60) as response:
            payload = response.read()
        if not payload.startswith(b"PK"):
            raise ValueError(f"ZIP이 아닌 응답입니다: {year}")
        destination.write_bytes(payload)
        manifest.append({"year": year, "name": destination.name, "bytes": len(payload),
                         "sha256": hashlib.sha256(payload).hexdigest()})
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

