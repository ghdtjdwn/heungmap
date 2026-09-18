# 다음 세션 인계

## 2026-09-18 종료 시점 (제출 2026-09-21)

- 서비스 모델: `regional-daily-1.0-e279d9027dff` — `data/processed/daily-forecast-production-v5/`(Git 제외).
  환경변수가 없으면 가장 번호가 큰 **채택** production 폴더를 자동 선택합니다.
- 자료 기준일 2026-08-19 → **마지막 예측 가능 행사일 2026-10-18**, 2026-10-19부터 모든 예측이 `unavailable`.
- 현재 모델 요약은 [MODEL_CARD.md](MODEL_CARD.md), 실행·평가·재현은 [MODEL_EVALUATION.md](MODEL_EVALUATION.md),
  이번 세션 기록은 [MODEL_SESSION_LOG_20260918.md](MODEL_SESSION_LOG_20260918.md), 결정은 DECISION_LOG D31.
- 작업 브랜치 `feat/model-submission-20260921`(push·PR은 사용자 확인 후).

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
- `verify_daily_model.py`: ready, 원본 checksum 4/4, 홀드아웃 재계산 일치, 온라인 예측 가능 234/264 시군구
- 실제 artifact + 격리 SQLite: 체험 로그인 → 기획 분석 200(강릉시, 신뢰도 보통, 문체부 81,266명) → 공개 200 →
  방문객 예측에서 같은 prediction ID·모델 버전·범위 확인. 실제 TourAPI 행사 100건 예측 조회 500 없음
  (available 30, 이미 시작·30일 초과 행사 등 설계상 unavailable 70). 화면 캡처 `docs/assets/submission-20260921/`.

## 시연·제출 전 할 일

1. 시연 당일 `PYTHONPATH=backend .venv/bin/python backend/scripts/verify_daily_model.py`가 ready인지 확인.
   샘플 행사는 오늘부터 30일 이내 시작, 신뢰도 높은 시군구(해운대구·제주시·수원시 등)로 고릅니다.
2. 새 방문자 자료가 공개되면(약 30일 지연) `refresh_daily_forecast.py` → `verify_daily_model.py`. 2~3주 간격.
   재학습 전에 `evaluate_frozen_daily_model.py --model-dir <현재 폴더>`로 전향 평가를 먼저 갱신합니다.
3. 발표·최종심사 날짜가 정해지면 그 날짜가 `last_predictable_target_date` − 30일 이전인지 확인합니다.
4. 서버 배포 시 Git 제외 artifact(production-v5, `mcst-attendance-lookup.csv`)를 복사하고 필요하면
   `HEUNGMAP_DAILY_MODEL_DIR`, `HEUNGMAP_MCST_LOOKUP_PATH`를 설정합니다.

## 남은 일 (제출 후)

- Windows 재현(`PLANNER_DEMO.md` 체크리스트), artifact 포장·서버 전달, LLM 고정 제약 위반 방어(평가 5개 중 1개 실패)
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
