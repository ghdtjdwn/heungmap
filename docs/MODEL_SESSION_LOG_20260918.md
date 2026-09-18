# 모델 제출 준비 세션 로그 — 2026-09-18

[MODEL_IMPLEMENTATION_SPEC.md](MODEL_IMPLEMENTATION_SPEC.md)의 Step별 실행 결과입니다.

## Step 0. 준비

- 시작: 2026-09-18 16:05 KST, 브랜치 `feat/model-submission-20260921` (기준 `336ab88`)
- backend 테스트: `124 passed` (시작 전)
- 채택 artifact `data/processed/daily-forecast-production-v3/` 6개 파일 확인

## Step 1. 방문자 자료 수집

- `data/raw/visitors-2026-aug-sep-refresh-20260918.jsonl` 신규(append-only), 3,228행
- 새 관측일: 2026-08-16~08-19 (4일, 일 807행 = 269시군구×3구분). 공표 지연 약 30일 재확인.

## Step 2. 동결 v3 전향 평가

- `backend/scripts/evaluate_frozen_daily_model.py`, 핵심 로직 `app/demand/forward_evaluation.py`
- 예측 수식을 `daily_service.predict_rows`로 추출해 서비스·평가가 공유
- 936행·234시군구: 모델 WAPE 4.434% vs 기준선 4.977% (10.90% 개선), RMSLE 0.09240 vs 0.09160(기준선 우세),
  ±20% 95.51% vs 96.05%, 80% 구간 포함률 75.53%

## Step 3. 모델 상태 점검

- `GET /api/v1/system/model-status`(계약 `ModelStatusResponse` 추가): ready/stale/unavailable, data_end,
  마지막 예측 가능 행사일, 노후까지 남은 일수. 경로·비밀값 미노출, 어떤 오류에도 200.
- `backend/scripts/verify_daily_model.py` 신규(기존 `verify_demand_model.py`는 D29 행사단위 모델용이라 유지)
- v3 점검: ready, days_until_stale 26, checksum 3/3, 홀드아웃 재계산 300행 일치, 온라인 가능 234/264 시군구
