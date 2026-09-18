#!/usr/bin/env sh
# 오라클 서버에서 실행: 이 폴더 하나 안에 전용 Python·가상환경을 만들고 모델 재학습을 매일 자동 실행하도록 등록한다.
# 시스템 Python·패키지를 건드리지 않으며 관리자 권한이 필요 없다. push.sh가 호출한다.
set -eu
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
TOOLS="$ROOT/.tools"
export UV_INSTALL_DIR="$TOOLS/bin" UV_PYTHON_INSTALL_DIR="$TOOLS/python" UV_CACHE_DIR="$TOOLS/cache" UV_NO_MODIFY_PATH=1

if [ ! -x "$TOOLS/bin/uv" ]; then
  echo "[1/5] uv 설치(이 폴더 안): $TOOLS/bin"
  curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null
else
  echo "[1/5] uv 있음"
fi
if [ ! -x "$ROOT/.venv/bin/python" ]; then
  echo "[2/5] Python 3.12 가상환경 생성(이 폴더 안)"
  "$TOOLS/bin/uv" venv --python 3.12 --python-preference only-managed "$ROOT/.venv" >/dev/null
else
  echo "[2/5] 가상환경 있음"
fi
echo "[3/5] 의존성 설치"
"$TOOLS/bin/uv" pip install --quiet --python "$ROOT/.venv/bin/python" -r backend/requirements-model.txt
"$ROOT/.venv/bin/python" -c "import lightgbm, pandas; print('     lightgbm', lightgbm.__version__, '/ pandas', pandas.__version__)"
[ -f "$ROOT/.env" ] && chmod 600 "$ROOT/.env"
echo "[4/5] 지금 한 번 실행(새 자료 수집·필요 시 재학습)"
sh "$ROOT/scripts/model-refresh.sh" >/dev/null 2>&1 || echo "     종료 코드 $? (0 정상, 4 곧 만료·모델 없음, 2 미채택, 1 오류) — 자세한 내용: data/processed/model-refresh-log.jsonl"
tail -1 "$ROOT/data/processed/model-refresh-log.jsonl" | "$ROOT/.venv/bin/python" -c "import json,sys; d=json.loads(sys.stdin.read()); a=d.get('after') or {}; print('     결과:', d.get('action') or d.get('error'), '| 모델', a.get('model_version'), '| 예측 가능 ~', a.get('last_predictable_target_date'), '| 만료까지', a.get('days_until_stale'), '일')"
echo "[5/5] 매일 06:30 자동 실행 등록"
sh "$ROOT/scripts/install-model-refresh.sh"
echo "완료. 이 폴더($ROOT)에 전부 있습니다. 지우기: 맥에서 scripts/oracle/remove.sh <서버>"
