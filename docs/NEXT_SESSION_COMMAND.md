# 다음 세션 인계

## 2026-09-20 Windows 최신화·재현

- PR #34(UI 디자인 개편)와 이후 PR #35~#44가 반영된 `main` `5260683`을 Windows 로컬에 동기화했습니다.
- backend `172 passed`, frontend typecheck·lint·production build, Playwright desktop·mobile `24 passed`를 확인했습니다.
- Windows 기본 CP949 때문에 UTF-8 모델 manifest fixture를 읽지 못하던 테스트 6개는 파일 인코딩을 명시해 수정했습니다.
- 오라클 서버 SSH는 timeout으로 직접 동기화하지 못했습니다. 대신 공식 append-only 재학습 경로로 2026-08-13 이후
  공개분 7,263행을 수집해 `regional-daily-1.0-123f612df871`을 로컬에서 채택했습니다. 자료 기준일은
  2026-08-21, 마지막 예측 가능일은 2026-10-20이며 `verify_daily_model.py`에서 261개 시군구가 모두
  `available`이었습니다.
- 로컬 출력 폴더명 `daily-forecast-production-v1`의 번호는 이 Windows 환경 안에서만 증가합니다. 서버의 `v6`와
  번호를 비교하지 않고 manifest의 `model_version`, `data_end`, checksum과 채택 상태를 기준으로 판별합니다.
- 원본 추가분과 모델 artifact는 기존 정책대로 Git에서 제외합니다. 실제 Google 로그인·운영 배포·실제 Claude 재평가는
  이번 Windows 검증에 포함하지 않았습니다.

## 2026-09-18 종료 시점 (제출 2026-09-21)

- 서비스 모델: `regional-daily-1.0-ab975d661247` — `data/processed/daily-forecast-production-v6/`(Git 제외).
  환경변수가 없으면 가장 번호가 큰 **채택** production 폴더를 자동 선택합니다.
- 자료 기준일 2026-08-19 → 이 맥의 모델로는 **2026-10-18까지** 예측됩니다. 오라클 서버 `ssumcp`가 매일 한국 04:30에 새 자료를
  받아 재학습하므로, 맥에서 최신 모델이 필요하면 `scripts/oracle/pull.sh ubuntu@100.97.34.28`로 가져옵니다.
- 현재 모델 요약은 [MODEL_CARD.md](MODEL_CARD.md), 실행·평가·재현은 [MODEL_EVALUATION.md](MODEL_EVALUATION.md),
  서버 재학습은 [ORACLE_MODEL_REFRESH.md](ORACLE_MODEL_REFRESH.md), 결정은 DECISION_LOG D30~D37.
- 모든 작업은 `main`에 병합됐습니다(PR #35~#43 이후 제출 정리 PR).

## 이번에 끝낸 일

- 새 방문자 자료 08-16~19 수집, 동결 v3 전향 평가(WAPE 4.434% vs 기준선 4.977%)
- 재학습 절차 고정(`refresh_daily_forecast.py`, 분할 자동, 새 폴더 강제) → v4 채택 → v5(지역별 신뢰도 메타데이터)
- `GET /api/v1/system/model-status`, `verify_daily_model.py`
- 지역별 신뢰도(홀드아웃 WAPE 5%/10%), 평소 대비 지역 방문수요 수준, TreeSHAP 요인 병합, 프론트 한 줄 표시
- TourAPI 축제 일정 feature 실험 → 개선 없어 미채택(D31)
- 문체부 보고 전년 방문객을 실제값 근거로 표시(TourAPI 2026 축제 32.8% 연결)
- 모델 카드, 발표 Q&A(PLANNER_DEMO) 갱신, 역할 확정(모델: 홍성주, 검토: 박지성)
- 기존 버그 수정: TourAPI homepage 설명문 때문에 행사 상세·예측이 500이던 문제

## 실제 검증 (2026-09-18)

- backend `147 passed`, frontend typecheck·lint·build 통과, Playwright `24 passed`
- `verify_daily_model.py`(v6): ready, 원본 checksum 4/4, 홀드아웃 재계산 일치, 선택 가능 261개 시군구 모두 온라인 예측 가능
- 실제 artifact + 격리 SQLite: 체험 로그인 → 기획 분석 200(강릉시, 신뢰도 보통, 문체부 81,266명) → 공개 200 →
  방문객 예측에서 같은 prediction ID·모델 버전·범위 확인. 실제 TourAPI 행사 100건 예측 조회 500 없음
  (available 30, 이미 시작·30일 초과 행사 등 설계상 unavailable 70). 화면 캡처 `docs/assets/submission-20260921/`.

## 2026-09-18 추가 반영

- Claude LLM(D32), 방문객 예측 구간 확대(실제 행사 30% → 88% 예측)와 흥행 진단 카드(D33). backend 157 passed, E2E 24 passed.

- 행정구역 개편 이력 연결 v6(실제 행사 98% 예측), 광주·전남 필터 복구, 재학습 자동화 `scripts/model-refresh.sh`, 공개 행사 근거(D34).
  서버 배포 시 cron 한 줄 등록이 필요합니다(MODEL_EVALUATION "재학습 절차").

- 화면 점검 수정(D35): 예시가 실제 예측을 내도록 수정, 방문객 목록 순서·연도 표시, 달력 3개+더보기, 수요 카드 접기, 랜딩 문구.

- Claude 보고서 안정화(D36): 실제 예시 4/4, 평가 5/5. `.env`의 `LLM_EFFORT=medium`.

- 재학습 자동 실행(D37): **오라클 서버만** 매일 재학습합니다. 맥 launchd는 해제했습니다. 맥에서 최신 모델이 필요하면
  `scripts/oracle/pull.sh ubuntu@100.97.34.28`.
  오라클 서버 `ssumcp`에 설치 완료: `~/heungmap-model`, 매일 한국 04:30 자동 재학습([ORACLE_MODEL_REFRESH.md](ORACLE_MODEL_REFRESH.md)).
  확인 `ssh ubuntu@100.97.34.28 'tail -1 ~/heungmap-model/data/processed/model-refresh-log.jsonl'`, 새 모델 가져오기 `scripts/oracle/pull.sh ubuntu@100.97.34.28`.

## 시연·제출 전 할 일

0. LLM은 Claude(D32·D36). 지금 `.env`는 `claude-sonnet-5`, effort medium. 발표 직전 `LLM_MODEL=claude-fable-5-1`로 바꾸고
   실제 예시 두 개를 브라우저에서 분석해 195초 안에 "LLM 기획 요약"이 나오는지 먼저 확인합니다(느리면 `LLM_EFFORT=low`). 이어서
   `evaluate_llm.py`로 5개 시나리오·응답 시간을 다시 확인합니다. 채팅에 노출된 API 키는 제출 전 Console에서 새로 발급해 교체합니다.

1. 시연 당일 `PYTHONPATH=backend .venv/bin/python backend/scripts/verify_daily_model.py`가 ready인지 확인.
   샘플 행사는 오늘부터 30일 이내 시작, 신뢰도 높은 시군구(해운대구·제주시·수원시 등)로 고릅니다.
2. 새 방문자 자료가 공개되면(약 30일 지연) `refresh_daily_forecast.py` → `verify_daily_model.py`. 2~3주 간격.
   재학습 전에 `evaluate_frozen_daily_model.py --model-dir <현재 폴더>`로 전향 평가를 먼저 갱신합니다.
3. 발표·최종심사 날짜가 정해지면 그 날짜가 `last_predictable_target_date` − 30일 이전인지 확인합니다.
4. 서버 배포 시 Git 제외 artifact(production-v5, `mcst-attendance-lookup.csv`)를 복사하고 필요하면
   `HEUNGMAP_DAILY_MODEL_DIR`, `HEUNGMAP_MCST_LOOKUP_PATH`를 설정합니다.

## 남은 일 (제출 후)

- artifact 포장·서버 전달, LLM 고정 제약 위반 방어(평가 5개 중 1개 실패)
- 동료 PR #29(역할 문서, 현재 역할과 다름)·#30(v2 NO-GO 실험) 정리 — 사용자 확인 후 닫기
- 비밀값·원본/가공 데이터·SQLite·모델·가상환경·캐시·빌드 결과는 계속 Git에서 제외합니다.

## 다음 세션 시작

```bash
git status --short --branch
PYTHONPATH=backend .venv/bin/pytest -q backend/tests
PYTHONPATH=backend .venv/bin/python backend/scripts/verify_daily_model.py
PYTHONPATH=backend .venv/bin/uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev
```
