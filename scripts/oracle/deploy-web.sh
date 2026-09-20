#!/usr/bin/env sh
# 맥에서 실행: 흥할지도 백엔드(FastAPI)를 오라클 서버 폴더 하나(기본 ~/heungmap-web)에 배포한다.
# 사용: scripts/oracle/deploy-web.sh <ssh 대상> <프론트 공개 주소>
#   예: scripts/oracle/deploy-web.sh ubuntu@100.97.34.28 https://heungmap.vercel.app
# 여러 번 실행해도 안전하다(코드·설정은 갱신, 서버가 쌓은 계정 DB는 덮어쓰지 않음).
#
# 재학습 폴더(~/heungmap-model)와의 관계:
#   data/processed 를 재학습 폴더로 심볼릭 링크한다. 매일 새벽 재학습이 새 모델을 만들면
#   백엔드가 번호가 가장 큰 채택본을 자동으로 골라 쓰므로 따로 옮길 필요가 없다.
set -eu
TARGET="${1:?ssh 대상을 주세요. 예: scripts/oracle/deploy-web.sh ubuntu@1.2.3.4 https://heungmap.vercel.app}"
ORIGIN="${2:?프론트 공개 주소를 주세요. 예: https://heungmap.vercel.app}"
DIR="${3:-heungmap-web}"
MODEL_DIR="${HEUNGMAP_MODEL_DIR_NAME:-heungmap-model}"
case "$DIR" in *[!A-Za-z0-9._-]*|""|.|..) echo "폴더 이름은 영문·숫자·._- 만 쓸 수 있습니다: $DIR" >&2; exit 1;; esac
case "$ORIGIN" in https://*|http://*) ;; *) echo "공개 주소는 http(s)://로 시작해야 합니다: $ORIGIN" >&2; exit 1;; esac
case "$ORIGIN" in */) echo "공개 주소 끝에 / 를 빼 주세요: $ORIGIN" >&2; exit 1;; esac

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
[ -f .env ] || { echo ".env가 없습니다." >&2; exit 1; }
[ -f data/processed/mcst-attendance-lookup.csv ] || { echo "data/processed/mcst-attendance-lookup.csv 가 없습니다." >&2; exit 1; }

echo "서버 $TARGET 의 ~/$DIR 에 백엔드를 배포합니다 (프론트 주소 $ORIGIN)"

ssh "$TARGET" "mkdir -p ~/$DIR/backend ~/$DIR/scripts/oracle ~/$DIR/data ~/$MODEL_DIR/data/processed"

# 1) 코드
rsync -az --delete --exclude '__pycache__' backend/app backend/scripts "$TARGET:~/$DIR/backend/"
rsync -az backend/requirements.txt backend/requirements-model.txt "$TARGET:~/$DIR/backend/"
rsync -az scripts/oracle/setup-web.sh scripts/oracle/check_web_data.py "$TARGET:~/$DIR/scripts/oracle/"
# 공통 계약. 계약 검증 테스트가 읽고, 서버에서 로컬과 같은 결과를 내려면 함께 있어야 한다.
rsync -az contracts/ "$TARGET:~/$DIR/contracts/"

# 2) 런타임 자료. 모델은 재학습 폴더를 그대로 쓰고, 문체부 표만 그 폴더에 함께 둔다.
rsync -az data/processed/mcst-attendance-lookup.csv "$TARGET:~/$MODEL_DIR/data/processed/"
# 계정·세션·공개 행사 DB는 서버에 쌓이므로 처음 한 번만 올린다.
rsync -az --ignore-existing data/heungmap.sqlite3 "$TARGET:~/$DIR/data/"
ssh "$TARGET" "ln -sfn ~/$MODEL_DIR/data/processed ~/$DIR/data/processed"
# 원본 방문자 자료도 재학습 폴더를 공유한다. API는 읽지 않지만 모델 검증 스크립트가 출처 checksum을 다시 계산한다.
ssh "$TARGET" "ln -sfn ~/$MODEL_DIR/data/raw ~/$DIR/data/raw"

# 3) 환경변수. 로컬 .env를 기준으로 배포용 값만 덮어쓴다.
#    HEUNGMAP_AUTH_MODE=mock 은 HEUNGMAP_ENV=development 에서만 허용된다(auth.py).
#    실제 Google 로그인은 이번 범위 밖이므로 mock을 유지한다.
{
  grep -v '^HEUNGMAP_PUBLIC_ORIGIN=' .env | grep -v '^HEUNGMAP_ENV=' | grep -v '^HEUNGMAP_AUTH_MODE='
  echo "HEUNGMAP_PUBLIC_ORIGIN=$ORIGIN"
  echo "HEUNGMAP_ENV=development"
  echo "HEUNGMAP_AUTH_MODE=mock"
} | ssh "$TARGET" "umask 077; cat > ~/$DIR/.env"

# 4) 설치·구동
ssh -t "$TARGET" "sh ~/$DIR/scripts/oracle/setup-web.sh"
