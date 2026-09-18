#!/usr/bin/env sh
# 맥에서 실행: 서버의 자동 실행을 해제하고 폴더를 통째로 지운다. 서버에 다른 흔적은 남지 않는다.
# 사용: scripts/oracle/remove.sh <ssh 대상> [폴더 이름]
set -eu
TARGET="${1:?ssh 대상을 주세요.}"
DIR="${2:-heungmap-model}"
case "$DIR" in *[!A-Za-z0-9._-]*|""|.|..) echo "잘못된 폴더 이름: $DIR" >&2; exit 1;; esac
ssh "$TARGET" "if [ -f ~/$DIR/scripts/install-model-refresh.sh ]; then sh ~/$DIR/scripts/install-model-refresh.sh --uninstall; fi; rm -rf ~/$DIR && echo '삭제했습니다: ~/$DIR'"
