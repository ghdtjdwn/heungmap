#!/usr/bin/env sh
# 맥에서 실행: 모델 재학습에 필요한 것만 오라클 서버의 폴더 하나(기본 ~/heungmap-model)에 올리고 자동 실행까지 설정한다.
# 사용: scripts/oracle/push.sh <ssh 대상(예: ubuntu@1.2.3.4 또는 ~/.ssh/config 별칭)> [폴더 이름]
# 여러 번 실행해도 안전하다(코드는 갱신, 서버가 새로 받은 자료·모델은 덮어쓰지 않음).
set -eu
TARGET="${1:?ssh 대상을 주세요. 예: scripts/oracle/push.sh ubuntu@1.2.3.4}"
DIR="${2:-heungmap-model}"
case "$DIR" in *[!A-Za-z0-9._-]*|""|.|..) echo "폴더 이름은 영문·숫자·._- 만 쓸 수 있습니다: $DIR" >&2; exit 1;; esac
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
KEY_LINE="$(grep '^VISITOR_API_SERVICE_KEY=' .env || true)"
[ -n "$KEY_LINE" ] || { echo ".env에 VISITOR_API_SERVICE_KEY가 없습니다." >&2; exit 1; }
MODEL="$(PYTHONPATH=backend .venv/bin/python -c 'from app.demand.daily_service import _directory; print(_directory().name)')"

echo "서버 $TARGET 의 ~/$DIR 에 올립니다 (현재 모델 $MODEL)"
ssh "$TARGET" "mkdir -p ~/$DIR/backend ~/$DIR/scripts/oracle ~/$DIR/data/raw ~/$DIR/data/processed"
rsync -az --delete --exclude '__pycache__' backend/app backend/scripts "$TARGET:~/$DIR/backend/"
rsync -az backend/requirements.txt backend/requirements-model.txt "$TARGET:~/$DIR/backend/"
rsync -az scripts/model-refresh.sh scripts/install-model-refresh.sh "$TARGET:~/$DIR/scripts/"
rsync -az scripts/oracle/ "$TARGET:~/$DIR/scripts/oracle/"
# 원본·모델은 추가만 한다. 서버가 이미 받은 새 자료와 새 모델 폴더는 건드리지 않는다.
rsync -az --ignore-existing data/raw/visitors-2025-full.jsonl data/raw/visitors-2026-jan-aug.jsonl data/raw/visitors-*-refresh-*.jsonl "$TARGET:~/$DIR/data/raw/"
rsync -az --ignore-existing "data/processed/$MODEL" "$TARGET:~/$DIR/data/processed/"
# 서버에는 방문자 API 키 한 줄만 둔다(LLM·지도 키 등은 올리지 않음).
printf '%s\n' "$KEY_LINE" | ssh "$TARGET" "umask 077; cat > ~/$DIR/.env"
ssh "$TARGET" "sh ~/$DIR/scripts/oracle/setup.sh"
