#!/usr/bin/env sh
# cron·launchd에서 매일 실행하는 모델 재학습 wrapper. 저장소 루트에서 가상환경 Python으로 실행한다.
# 예) crontab -e →  30 6 * * * /절대경로/heungmap/scripts/model-refresh.sh >> /절대경로/heungmap/data/processed/model-refresh-cron.log 2>&1
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYTHONPATH=backend exec "$ROOT/.venv/bin/python" backend/scripts/scheduled_refresh.py "$@"
