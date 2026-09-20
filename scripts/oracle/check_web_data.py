"""배포한 백엔드가 로컬과 같은 모델·자료를 보고 있는지 확인한다. setup-web.sh가 부른다."""

from __future__ import annotations

import os
import pathlib

from dotenv import load_dotenv

load_dotenv(pathlib.Path(".env"))

from app.attendance.lookup import DEFAULT_PATH as MCST_DEFAULT
from app.demand.daily_service import _directory

directory = _directory()
print("     모델 폴더:", directory)
print("     실제 위치:", pathlib.Path(directory).resolve())

lookup = pathlib.Path(os.environ.get("HEUNGMAP_MCST_LOOKUP_PATH", str(MCST_DEFAULT)))
print("     문체부 전년 방문객 표:", lookup, "— 존재" if lookup.exists() else "— 없음(확인 필요)")

db = pathlib.Path(os.environ.get("HEUNGMAP_DB_PATH", "data/heungmap.sqlite3"))
print("     계정·공개 DB:", db, "— 존재" if db.exists() else "— 새로 생성됨")

print("     공개 origin:", os.environ.get("HEUNGMAP_PUBLIC_ORIGIN", "(미설정)"))
print("     인증 모드:", os.environ.get("HEUNGMAP_AUTH_MODE", "mock"))
