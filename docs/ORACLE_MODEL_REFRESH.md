# 오라클 서버에서 모델 자동 재학습

모델이 예측에 쓰는 방문자 자료는 약 30일 늦게 공개되고, 자료 마지막 날 + 60일까지만 예측할 수 있습니다.
그래서 새 자료를 계속 받아 재학습해야 합니다(이유: [MODEL_CARD.md](MODEL_CARD.md) §10, [MODEL_EVALUATION.md](MODEL_EVALUATION.md)
"재학습 절차"). 아래 명령은 이 일을 오라클 서버가 **사람 개입 없이 매일** 하게 만듭니다.

## 원칙: 폴더 하나

서버에는 `~/heungmap-model` 폴더 하나만 생깁니다. 지울 때는 이 폴더와 cron 한 줄만 없애면 흔적이 남지 않습니다.

```text
~/heungmap-model/
├── backend/            재학습에 필요한 코드만(웹 화면 코드 없음)
├── scripts/            model-refresh.sh, install-model-refresh.sh, oracle/
├── .tools/             이 폴더 전용 uv와 Python 3.12 (서버 시스템 Python을 쓰지 않음)
├── .venv/              이 폴더 전용 가상환경
├── .env                방문자 API 키 한 줄만(권한 600). LLM·지도 키는 올리지 않음
└── data/
    ├── raw/            방문자 원본(새로 받은 파일이 매일 추가됨)
    └── processed/      모델 폴더(daily-forecast-production-v*), 실행 기록
```

서버 밖에 남는 것은 사용자 crontab의 한 줄(`# heungmap-model-refresh` 표시)뿐입니다. 관리자 권한(sudo)은 필요 없습니다.

## 명령 (모두 맥의 저장소 루트에서)

`<서버>`는 평소 `ssh`로 접속할 때 쓰는 대상입니다. 예: `ubuntu@123.45.67.89`, `opc@...`, 또는 `~/.ssh/config` 별칭.

| 하고 싶은 일 | 명령 |
| --- | --- |
| 처음 설치·코드 갱신 | `scripts/oracle/push.sh <서버>` |
| 서버가 만든 새 모델을 맥으로 가져오기 | `scripts/oracle/pull.sh <서버>` |
| 서버에서 완전히 지우기 | `scripts/oracle/remove.sh <서버>` |

`push.sh`가 하는 일:

1. 폴더를 만들고 재학습 코드·스크립트를 올립니다.
2. 방문자 원본과 현재 채택 모델을 **추가만** 합니다(서버가 이미 받은 새 자료·새 모델은 덮어쓰지 않음).
3. `.env`에 `VISITOR_API_SERVICE_KEY` 한 줄만 씁니다.
4. 서버에서 `scripts/oracle/setup.sh`를 실행합니다.
   - 폴더 안에 uv·Python 3.12·가상환경을 만들고 의존성을 설치합니다.
   - 한 번 실행해 결과(모델, 예측 가능 마지막 날, 만료까지 남은 일수)를 보여 줍니다.
   - 매일 한국 시간 04:30 자동 실행을 등록합니다(서버 시계가 UTC면 cron에는 19:30). CPU 우선순위를 낮춰(`nice`) 같은
     서버의 다른 서비스를 방해하지 않습니다.

여러 번 실행해도 안전합니다. 코드를 고친 뒤에도 같은 명령으로 갱신합니다.

## 잘 돌고 있는지 확인

```bash
ssh <서버> 'tail -1 ~/heungmap-model/data/processed/model-refresh-log.jsonl'
ssh <서버> 'crontab -l | grep heungmap'
```

실행 기록 한 줄의 `action`이 `none`(새 자료 부족)이나 `retrained`(재학습)이고 `after.status`가 `ready`면 정상입니다.
종료 코드는 0 정상, 2 재학습했지만 채택 기준 미달(이전 모델 유지), 4 만료 14일 이내·모델 없음, 1 오류입니다.

## 서버 요구 사항

- 리눅스(Ubuntu·Oracle Linux, x86_64·ARM 모두 가능), 인터넷으로 나가는 연결(공공데이터포털·uv·PyPI)
- `crontab` 명령. 없으면 Ubuntu는 `sudo apt install cron`, Oracle Linux는 `sudo dnf install cronie && sudo systemctl enable --now crond`
- 디스크 약 1GB(원본 100MB대, 모델 폴더 하나 약 25MB, Python·패키지)
- 방문자 원본 수집은 바깥으로 나가는 요청만 하므로 방화벽 포트를 열 필요가 없습니다.

## 웹 서비스와의 관계

이 폴더는 **재학습 전용**입니다. 나중에 같은 서버에 웹 서비스를 배포하면 백엔드 환경변수
`HEUNGMAP_DAILY_MODEL_DIR`을 쓰지 말고, 서비스의 `data/processed`가 이 폴더의 `data/processed`를 가리키게 하거나(심볼릭 링크)
`pull.sh`처럼 새 모델 폴더를 복사해 두면 서비스가 가장 최근 채택 모델을 자동으로 고릅니다.

## 검증 (2026-09-18)

실제 서버 대신 맥 안의 가짜 홈 폴더와 `ssh`·`rsync`·`crontab` 대역으로 전체 흐름을 확인했습니다.
push(43초, 폴더 안 Python 3.12 설치·의존성·1회 실행·cron 등록) → 재실행(cron 한 줄 유지) → pull → remove(폴더 삭제, 다른
cron 작업 보존). 실제 오라클 서버에서의 첫 실행은 사용자가 `push.sh`로 진행합니다.
