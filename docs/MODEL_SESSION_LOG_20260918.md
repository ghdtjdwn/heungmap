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

## Step 4. 재학습 절차 고정 + v4

- 명세 정정: 명세의 `validation_start = test_start − 2개월`은 v3 실제 분할(07-01/08-01)과 달라
  **−1개월**(시험 직전 두 달 전진 검증창)로 구현했습니다.
- `forecasting.default_split_dates`, `app/demand/daily_training.py`(train_daily_model, next_production_directory),
  `training_inputs.latest_raw_date`, `scripts/refresh_daily_forecast.py` 신규, `train_daily_forecast.py` 공용 절차 사용
- 수집은 마지막 원본 기준일 다음 날부터만(겹침 → 값 충돌 방지). 새 날짜 없으면 종료 코드 3.
- `daily_service._directory()`: 환경변수 없으면 가장 번호가 큰 채택 production-v* 자동 선택
- v4 `regional-daily-1.0-e279d9027dff`: 채택. 홀드아웃(08-01~19, 4,446행) WAPE 3.939% vs 기준선 4.260%,
  80% 구간 77.64%. data_end 08-19 → 마지막 예측 가능 행사일 10-18. verify ready, checksum 4/4.

## Step 5 + Step 8. 지역별 신뢰도·수요 수준, 요인 병합

- manifest에 `regions[].holdout_wape/holdout_days`, `confidence_thresholds`, `demand_level_percentiles` 추가
  (schema_version 1.0 유지, 키 없는 이전 artifact는 기존 동작)
- `daily_service.region_confidence`, `regional_demand_level`, `merged_factors`; evidence `ev_daily_region_holdout`,
  `ev_daily_demand_level`; 요인 설명을 "LightGBM TreeSHAP 기여도"로 명시하고 같은 라벨 합산
- v5 재학습(같은 자료): 모델 파일·버전 v4와 동일, 신뢰도 high 150 / medium 62 / low 52
- 프론트: `demandLevelText`로 "평소 대비 지역 방문수요: …(현장 혼잡도 아님)" 한 줄, 방문객 상세에 예측 근거 목록. tsc·lint 통과

## Step 6. TourAPI 축제 일정 feature 실험 (v1.1) — 미채택

- `app/demand/festivals.py`(calendar_from_items, load_festival_calendar, festival_features), forecasting에 선택적
  feature 목록, `daily_training.add_festival_ablation`(6번째 조건), `train_daily_forecast.py --festivals`
- 전년 축제 수 feature는 제외(2024·2025 조회 5·243건, TourAPI가 지난 회차를 올해 일정으로 덮어씀)
- 결과: 6/6 형식 통과. 검증 WAPE 4.0575% vs 4.0594%, 시험 3.9414% vs 3.9388%(축제 입력이 근소하게 나쁨),
  축제 진행일 494행에서도 개선 없음, 축제 입력 TreeSHAP 비중 1.1%
- 결정: 이득이 잡음 수준이고 실시간 TourAPI 의존만 늘어 서비스 미연결(명세 6-c 연결 작업은 수행하지 않음)

## Step 7. 문체부 전년 실적 표시

- `app/attendance/lookup.py`, `scripts/build_mcst_lookup.py`; planner·방문객 예측에 `ev_mcst_prior_attendance`(verified_fact)
- 조회표 3,184개 축제. TourAPI 2026 축제 445건 중 146건(32.8%) 정확 일치(최근 3년 실적만)
- 명세 보완: `canonical_title`이 "2026년"의 "년"을 남겨 조회용 `lookup_key`에서 제거. 광역 주관(시군구 빈칸) 행사 허용.
- 테스트는 conftest가 조회표 경로를 없는 파일로 지정해 로컬 자료와 격리

## Step 8. 설명 계층 문서화

- 코드는 Step 5 커밋에 포함(같은 라벨 합산, "LightGBM TreeSHAP 기여도" 설명)
- `PLANNER_DEMO.md` 발표 Q&A를 현재 모델 기준으로 갱신(옛 "학습 모델·SHAP 없음" 답변 교체, 정확도·축제 입력·노후화 질문 추가,
  시연 전 `verify_daily_model.py` 확인, 신뢰도 높은 시군구 예시는 v5 manifest로 확인)
- `MODEL_PLAN.md` 권장 구조 위에 실제 채택 구조 안내

## Step 9. 모델 카드

- `docs/MODEL_CARD.md`: 대상·비대상, 버전(v3/v4/v5/실험), 구조, 입력, 자료, 분할·채택 기준, 후향·전향·규모별 성능,
  축제 실험, 신뢰도 규칙, 한계, 재학습 명령, 발표 표현 지침. 수치는 evaluation.json·forward-evaluation JSON에서 옮김.

## Step 10. 문서·역할 정리

- `TEAM_WORKFLOW.md`·`00_START_HERE.md` 역할: 예측 계약·AI 모델 홍성주, 통합 검토 박지성
- `DECISION_LOG.md` D31, `MODEL_PLAN.md` 담당 확정, `NEXT_SESSION_COMMAND.md` 전면 갱신, WORK_PLAN 완료 표시
- PR #29·#30 닫기는 [STOP] — 사용자 확인 대기

## Step 11. 전체 검증

- backend 147 passed, frontend typecheck·lint·build 통과, Playwright 24 passed
- verify_daily_model(v5) ready, checksum 4/4, 재계산 일치, 온라인 234/264
- 실제 artifact + 격리 SQLite 흐름: 분석 200(강릉시 p50 539,482 방문자-일, 신뢰도 보통, 수준 낮음, 문체부 81,266명) → 공개 200 →
  방문객 예측 prediction ID·모델 버전·범위 일치(공개 시 근거는 기존 설계대로 비움)
- 실제 TourAPI 행사 100건: 처음 1건이 500 → 원인은 기존 코드의 homepage 설명문 URL 검증 실패. 수정 후 500 없음,
  available 30 / unavailable 70(이미 시작 58, 30일 초과 2, 광역 단위 10 — 모두 설계상 범위 밖)
- 화면 캡처 3장 `docs/assets/submission-20260921/`
