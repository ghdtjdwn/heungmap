#!/usr/bin/env sh
# 모델 재학습(scripts/model-refresh.sh)을 매일 자동 실행하도록 등록한다. 여러 번 실행해도 한 번만 등록된다.
#   리눅스 서버: crontab에 매일 06:30 실행을 추가
#   macOS:      ~/Library/LaunchAgents에 매일 06:30 실행(launchd)을 추가. 맥이 잠자고 있었으면 깨어난 뒤 실행
# 해제: scripts/install-model-refresh.sh --uninstall
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$ROOT/scripts/model-refresh.sh"
LOG="$ROOT/data/processed/model-refresh-cron.log"
MARK="# heungmap-model-refresh"
LABEL="kr.heungmap.model-refresh"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ "${1:-}" != "--uninstall" ] && [ ! -x "$ROOT/.venv/bin/python" ]; then
  echo "가상환경(.venv)이 없습니다. 저장소 루트에서 python3 -m venv .venv 와 의존성 설치를 먼저 하세요." >&2
  exit 1
fi
if [ "$(uname)" != "Darwin" ] && ! command -v crontab >/dev/null 2>&1; then
  echo "crontab 명령이 없습니다. Ubuntu: sudo apt install cron / Oracle Linux: sudo dnf install cronie && sudo systemctl enable --now crond" >&2
  exit 1
fi
mkdir -p "$ROOT/data/processed"

if [ "$(uname)" = "Darwin" ]; then
  if [ "${1:-}" = "--uninstall" ]; then
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    rm -f "$PLIST"
    echo "해제했습니다: $PLIST"
    exit 0
  fi
  mkdir -p "$HOME/Library/LaunchAgents"
  cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>/bin/sh</string><string>$SCRIPT</string></array>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>6</integer><key>Minute</key><integer>30</integer></dict>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict>
</plist>
PLIST_EOF
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$PLIST"
  echo "등록했습니다(macOS launchd, 매일 06:30): $PLIST"
  echo "확인: launchctl print gui/$(id -u)/$LABEL | grep -E 'state|path'"
  exit 0
fi

CURRENT="$(crontab -l 2>/dev/null || true)"
FILTERED="$(printf '%s\n' "$CURRENT" | grep -v "$MARK" || true)"
if [ "${1:-}" = "--uninstall" ]; then
  printf '%s\n' "$FILTERED" | crontab -
  echo "해제했습니다(crontab)."
  exit 0
fi
LINE="30 6 * * * $SCRIPT >> $LOG 2>&1 $MARK"
printf '%s\n%s\n' "$FILTERED" "$LINE" | sed '/^$/d' | crontab -
echo "등록했습니다(crontab, 매일 06:30):"
crontab -l | grep "$MARK"
