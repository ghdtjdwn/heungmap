#!/usr/bin/env sh
# 오라클 서버에서 실행: 흥할지도 백엔드(FastAPI)를 이 폴더 안의 전용 Python으로 구동하고
# systemd 서비스로 등록한다. deploy-web.sh가 호출한다.
#
# 로컬(맥)과 같게 유지하는 것:
#   - Python 3.12 + backend/requirements-model.txt 고정 버전
#   - uvicorn worker 1개. app.main 이 분석 결과를 프로세스 메모리(analysis_cache)에 들고 있어
#     worker를 늘리면 "분석 → 공개" 흐름이 로컬과 달라진다.
#   - 환경변수는 systemd가 아니라 앱이 직접 읽는다(main.py의 load_dotenv). systemd EnvironmentFile은
#     주석·따옴표 처리가 달라 .env를 그대로 넣으면 파싱이 어긋날 수 있다.
set -eu
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
MODEL_ROOT="${HEUNGMAP_MODEL_ROOT:-$HOME/heungmap-model}"
TOOLS="$MODEL_ROOT/.tools"
export UV_INSTALL_DIR="$TOOLS/bin" UV_PYTHON_INSTALL_DIR="$TOOLS/python" UV_CACHE_DIR="$TOOLS/cache" UV_NO_MODIFY_PATH=1

[ -x "$TOOLS/bin/uv" ] || { echo "uv가 없습니다. 먼저 scripts/oracle/push.sh 로 재학습 폴더를 설치하세요." >&2; exit 1; }

if [ ! -x "$ROOT/.venv/bin/python" ]; then
  echo "[1/4] Python 3.12 가상환경 생성(이 폴더 안)"
  "$TOOLS/bin/uv" venv --python 3.12 --python-preference only-managed "$ROOT/.venv" >/dev/null
else
  echo "[1/4] 가상환경 있음"
fi

echo "[2/4] 의존성 설치(backend/requirements-model.txt)"
"$TOOLS/bin/uv" pip install --quiet --python "$ROOT/.venv/bin/python" -r backend/requirements-model.txt

# LightGBM은 OpenMP(libgomp)가 필요하다. 재학습 폴더가 이미 받아 둔 것을 함께 쓴다.
[ -d "$TOOLS/lib" ] && export LD_LIBRARY_PATH="$TOOLS/lib:${LD_LIBRARY_PATH:-}"
PYTHONPATH=backend "$ROOT/.venv/bin/python" -c "import lightgbm, pandas, fastapi; print('     lightgbm', lightgbm.__version__, '/ pandas', pandas.__version__, '/ fastapi', fastapi.__version__)"

[ -f "$ROOT/.env" ] && chmod 600 "$ROOT/.env"
chmod 600 "$ROOT/data/heungmap.sqlite3" 2>/dev/null || true

echo "[3/4] 채택 모델과 데이터 확인"
PYTHONPATH=backend "$ROOT/.venv/bin/python" "$ROOT/scripts/oracle/check_web_data.py"

echo "[4/4] systemd 서비스 등록(heungmap-api, 127.0.0.1:8000, worker 1개)"
sudo tee /etc/systemd/system/heungmap-api.service >/dev/null <<UNIT
[Unit]
Description=HeungMap API (FastAPI)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$(id -un)
Group=$(id -gn)
WorkingDirectory=$ROOT
Environment=PYTHONPATH=$ROOT/backend
Environment=PYTHONUNBUFFERED=1
Environment=LD_LIBRARY_PATH=$TOOLS/lib
ExecStart=$ROOT/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
Restart=always
RestartSec=5
# 같은 서버의 다른 서비스를 방해하지 않도록 우선순위를 낮춘다.
Nice=5
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable heungmap-api
# 이미 돌고 있으면 enable --now는 재시작하지 않는다. .env·코드 변경을 반영하려면 restart가 필요하다.
sudo systemctl restart heungmap-api
sleep 5
systemctl is-active heungmap-api || true
if ! curl -sS --max-time 15 http://127.0.0.1:8000/api/v1/health; then
  echo
  echo "health 실패 — 최근 로그:" >&2
  sudo journalctl -u heungmap-api -n 40 --no-pager >&2
  exit 1
fi
echo
echo "완료. 로그: sudo journalctl -u heungmap-api -f"
