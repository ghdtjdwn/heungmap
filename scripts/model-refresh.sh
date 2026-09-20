#!/usr/bin/env sh
# cron·launchd에서 매일 실행하는 모델 재학습 wrapper. 저장소 루트에서 가상환경 Python으로 실행한다.
# 예) crontab -e →  30 6 * * * /절대경로/heungmap/scripts/model-refresh.sh >> /절대경로/heungmap/data/processed/model-refresh-cron.log 2>&1
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# 오라클 서버처럼 시스템에 libgomp가 없으면 setup.sh가 폴더 안(.tools/lib)에 둔 것을 쓴다.
if [ -d "$ROOT/.tools/lib" ]; then export LD_LIBRARY_PATH="$ROOT/.tools/lib:${LD_LIBRARY_PATH:-}"; fi
# 다른 서비스와 같은 서버에서 돌 수 있으므로 CPU 우선순위를 낮춘다.
PYTHONPATH=backend exec nice -n 10 "$ROOT/.venv/bin/python" backend/scripts/scheduled_refresh.py "$@"
