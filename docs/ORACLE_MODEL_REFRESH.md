# 운영 서버의 모델 자동 재학습

모델이 예측에 쓰는 방문자 자료는 약 30일 늦게 공개되고, 자료 마지막 날 + 60일까지만 예측할 수 있습니다(이유: [MODEL_CARD.md](MODEL_CARD.md) §10,
[MODEL_EVALUATION.md](MODEL_EVALUATION.md) "재학습 절차"). 그래서 새 자료를 계속 받아 재학습해야 하고, 이 일은 운영 서버가 **사람 개입 없이 매일**
합니다. compose·systemd·이미지 빌드 같은 실행 정의는 비공개 인프라 저장소에서 관리하며, 이 문서는 공개 저장소의 코드와 맞닿는 부분을 일반화해 적습니다.
서버 주소·계정·경로는 적지 않고 `<서버>`·`<데이터 폴더>`로 씁니다.

## 구조 (2026-10-15부터)

2026-09-18~10-14의 "폴더 하나 + 사용자 crontab" 방식(아래 "이전 방식")을 서버 이관과 함께 Docker Compose + systemd 타이머로 바꿨습니다.

- **이미지 하나**: 백엔드 API와 재학습 작업이 같은 이미지를 씁니다. 이미지는 이 저장소의 **고정 커밋**을 깨끗하게 checkout해 ARM64 맥에서 빌드하고
  (`heungmap:<커밋 12자리>` 태그), 레지스트리 없이 tar로 서버에 옮겨 `docker load`합니다. 이미지 안 `/app`에는 `backend/app`, `backend/scripts`,
  `contracts`가 들어가고, Python 3.12 가상환경에 `backend/requirements-model.txt`를 전이 의존성까지 버전 고정해 설치합니다. LightGBM이 쓰는 `libgomp`는
  이미지에 설치돼 있습니다.
- **Compose 프로젝트 하나, 서비스 둘**: 상주 `api`(uvicorn worker 1개, 메모리 상한 512MB, 재시작 정책 unless-stopped)와 하루 1회 일회성
  `refresh`(compose profile로 분리해 평소에는 컨테이너가 없음, 메모리 상한 1GB, `nice -n 10`, 재시작 없음). 두 서비스 모두 컨테이너 시간대는 UTC입니다
  (이전 서버와 같은 날짜 경계를 쓰기 위한 의도적 선택. 재학습의 `today`와 원본 파일 이름이 UTC 날짜가 됩니다).
- **systemd 타이머**: 매일 **04:30 KST(19:30 UTC)**에 `docker compose run --rm refresh`를 한 번 실행합니다(`Persistent=true`라 꺼져 있던 시간을 지나면
  부팅 뒤 따라잡음). 컨테이너 안에서 도는 명령은 `backend/scripts/scheduled_refresh.py` 하나뿐입니다. 표준출력은 데이터 폴더의
  `processed/model-refresh-cron.log`에 덧붙입니다.
- **데이터 볼륨**: 서버의 한 폴더가 컨테이너의 `/app/data`로 들어갑니다.

  ```text
  <데이터 폴더>/
  ├── raw/         visitors-<시작>-<끝>-refresh-<실행일>.jsonl  방문자 원본(append-only, 매일 1개 추가)
  ├── processed/   daily-forecast-production-v*/              모델 폴더(번호 증가, 지우지 않음)
  │                mcst-attendance-lookup.csv                 문체부 전년 방문객 조회표
  │                model-refresh-log.jsonl                    실행마다 JSON 한 줄(아래 "기록 읽는 법")
  │                model-refresh-cron.log                     사람이 읽는 출력(타이머가 덧붙임)
  └── db/          heungmap.sqlite3                           계정·세션·공개 행사 DB(API만 씀)
  ```

  API는 `processed`·`raw`를 **읽기 전용**으로, refresh는 읽기·쓰기로 마운트합니다. 같은 폴더를 보므로 refresh가 새 채택 폴더를 만들면 **실행 중인 API가
  재시작 없이** 번호가 가장 큰 채택본을 집습니다(`daily_service.select_production_directory`).
- 재학습 컨테이너에 들어가는 비밀값은 방문자 API 키 하나뿐입니다. LLM·지도·OAuth 키는 API 컨테이너에만 있습니다.

## 재학습 작업이 매일 하는 일 (`scheduled_refresh.py` → `app/demand/refresh.py`)

1. **수집**: 마지막 원본 기준일 다음 날부터 오늘까지를 새 파일로 받습니다. 기존 파일은 고치지 않고 겹쳐 받지 않습니다. 공표 지연 때문에 보통 하루에
   1일치가 새로 들어옵니다.
2. **판단**: 모델 기준일보다 7일 이상 새 자료가 쌓였거나, 노후까지 21일 이하인데 새 자료가 하루라도 있으면 재학습합니다. 아니면 `action: none`.
3. **전향 평가**: 재학습 전에 현재 모델을 새 관측일로 채점해 현재 모델 폴더에 `forward-evaluation-<날짜>.json`으로 남깁니다.
4. **재학습**: 다음 번호 `daily-forecast-production-v<N+1>`에 학습·평가·저장합니다.
5. **채택 판단**: 5개 조건을 모두 통과하면 정식 채택(`adoption_mode: full`). 아니면 현재 모델이 노후까지 14일 이하(또는 이미 노후·없음)이고 후보가
   1차 조건 3개를 통과했을 때만 임시 채택(`provisional`), 그 밖에는 미채택(`rejected`, 이전 모델 유지). 규칙과 이유는
   [MODEL_EVALUATION.md](MODEL_EVALUATION.md) "임시 채택 규칙"(D39).
6. **기록·종료 코드**: 결과를 `model-refresh-log.jsonl`에 한 줄로 덧붙이고 종료합니다. 0 정상, 2 재학습했지만 미채택, 4 노후 14일 이내·노후·모델 없음,
   1 오류. 0이 아니면 systemd unit이 `failed`로 남아 `systemctl --failed`에 보입니다(실패 알림은 따로 없습니다).

## 기록 읽는 법

`processed/model-refresh-log.jsonl`의 마지막 줄 하나로 그날 무슨 일이 있었는지 알 수 있습니다.

| 필드 | 뜻 |
| --- | --- |
| `run_at`, `today` | 실행 시각(UTC)과 작업이 본 오늘 날짜 |
| `collection` | `collected`(새 파일 이름, 받은 기간) / `no_new_data` / `skipped` |
| `before` | 실행 전 모델 상태(`status`, `model_version`, `data_end`, `days_until_stale`) |
| `latest_raw_date`, `new_days` | 원본 마지막 날짜와 모델 기준일 대비 새 일수 |
| `forward_evaluation` | 현재 모델의 새 날짜 채점(`period`, `model_wape`, `baseline_wape`, `rows`) |
| `training` | 새 후보의 분할·홀드아웃 성능·`checks`(조건별 통과 여부)·`model_adopted`·`adoption_mode`·`failed_checks` |
| `action` | `none` 또는 `retrained` |
| `after` | 실행 후 모델 상태. `adoption_mode`가 `full`/`provisional`인지, `last_predictable_target_date`가 늘었는지 본다 |
| `error`, `message` | 예외로 끝났을 때만 |

정상인 날은 `action`이 `none`(새 자료 부족)이거나 `retrained`이고 `after.status`가 `ready`입니다. `training.model_adopted`가 `false`인 날이 이어지면
`training.checks`에서 어떤 조건이 떨어지는지 보고, `after.days_until_stale`이 14 이하로 내려가면 다음 실행에서 임시 채택 규칙이 작동합니다.

```bash
ssh <서버> 'sudo journalctl -u heungmap-refresh -n 40 --no-pager'          # 실행 출력·종료 코드
ssh <서버> 'systemctl list-timers heungmap-refresh.timer --no-pager'        # 다음 실행 시각
ssh <서버> 'tail -1 <데이터 폴더>/processed/model-refresh-log.jsonl'          # 그날의 판단 한 줄
sudo systemctl start heungmap-refresh.service                                # 수동으로 한 번 더(매일 실행해도 안전)
curl -s https://heungmap.ssumcp.duckdns.org/api/v1/system/model-status       # API가 보는 모델
```

`model-status`는 `status`(ready/stale/unavailable), `model_version`, `data_end`, `last_predictable_target_date`, `days_until_stale`, `regions`에 더해
`adoption_mode`와 `failed_checks`를 돌려줍니다. 파일 경로·비밀값은 넣지 않습니다.

## 알아 둘 것

- 재학습 컨테이너가 OOM 등으로 죽으면 `processed/.model-refresh.lock`이 남아 다음 실행이 "다른 재학습 작업이 실행 중" 오류로 끝납니다. 실행 중인
  컨테이너가 없는 것을 확인하고 지웁니다.
- 1 vCPU 서버에서 전체 재학습은 약 1.5분, 피크 메모리 약 800MB(2026-10-15 실측)입니다. 다른 서비스의 무거운 주기 작업과 겹치지 않게 04:30으로 두었습니다.
- 모델 폴더(약 25MB/개)와 원본 파일을 지우는 장치는 없습니다. 디스크를 가끔 확인합니다.
- 코드가 바뀌어도 재학습 작업은 **이미지를 새로 빌드해 올리기 전까지** 이전 코드로 돕니다. 반영 절차는 [DEPLOY_RUNBOOK.md](DEPLOY_RUNBOOK.md).

## 이전 방식 (2026-09-18 ~ 2026-10-14)

서버의 재학습 전용 폴더 하나에 재학습 코드·전용 uv·Python·가상환경·원본·모델을 두고 사용자 crontab 한 줄(`30 19 * * *`)로 `scripts/model-refresh.sh`를
실행했습니다. 설치·동기화·삭제는 `scripts/oracle/push.sh`·`pull.sh`·`remove.sh`, 로컬 등록은 `scripts/install-model-refresh.sh`가 맡았습니다(D34·D37).
이 스크립트들은 기록으로 저장소에 남아 있지만 현재 운영 경로가 아닙니다. 2026-09-20 배포 때 `+x` 권한 누락으로 cron이 이틀 실패한 뒤 `/bin/sh <스크립트>`
형태로 고친 일은 [DEPLOY_RUNBOOK.md](DEPLOY_RUNBOOK.md) "2026-09-20 첫 배포 기록"에 있습니다.
