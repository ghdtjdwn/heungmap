#!/usr/bin/env sh
# 맥에서 실행: 서버가 자동으로 받은 새 방문자 자료와 새 모델 폴더, 실행 기록을 이 저장소로 가져온다(기존 파일은 덮어쓰지 않음).
# 사용: scripts/oracle/pull.sh <ssh 대상> [폴더 이름]
set -eu
TARGET="${1:?ssh 대상을 주세요.}"
DIR="${2:-heungmap-model}"
case "$DIR" in *[!A-Za-z0-9._-]*|""|.|..) echo "잘못된 폴더 이름: $DIR" >&2; exit 1;; esac
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
rsync -az --ignore-existing --include 'visitors-*-refresh-*.jsonl' --exclude '*' "$TARGET:~/$DIR/data/raw/" data/raw/
rsync -az --ignore-existing --include 'daily-forecast-production-v*/***' --exclude '*' "$TARGET:~/$DIR/data/processed/" data/processed/
rsync -az "$TARGET:~/$DIR/data/processed/model-refresh-log.jsonl" data/processed/model-refresh-log.server.jsonl
PYTHONPATH=backend .venv/bin/python -c "from app.demand.daily_service import model_status; s=model_status(); print('이 컴퓨터가 쓰는 모델:', s.get('model_version'), '| 예측 가능 ~', s.get('last_predictable_target_date'))"
