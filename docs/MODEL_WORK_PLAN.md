# AI 모델 담당 작업 설계 — 2026-09-18

이 문서는 **AI 모델 담당(홍성주)이 제출 전까지 해야 할 일 전부**를 우선순위대로 적은 실행 설계서입니다.
설계는 Fable이, 구현은 다음 세션의 Opus가 맡습니다. 각 작업은 "왜 → 무엇을 → 어디를 → 완료 조건 → 검증"
순서로 적었고, 한 작업이 끝날 때마다 backend 테스트(`PYTHONPATH=backend .venv/bin/pytest -q backend/tests`)가
통과해야 다음으로 넘어갑니다.

현재 상태의 근거는 [MODEL_EVALUATION.md](MODEL_EVALUATION.md)와 [DECISION_LOG.md](DECISION_LOG.md) D29·D30입니다.
**구현은 [MODEL_IMPLEMENTATION_SPEC.md](MODEL_IMPLEMENTATION_SPEC.md)의 Step 0~12를 순서대로 따릅니다** (파일·함수·테스트·명령까지 지정).

## ✅ 2026-09-18 실행 결과

T1(재학습 절차·v4/v5) · T2(전향 평가) · T3(상태 endpoint) · T5(지역별 신뢰도·수요 수준) · T6(문체부 실제값) ·
T7(요인 병합·TreeSHAP 표기) · T8(모델 카드) · T9(역할·문서, PR #29·#30 닫기는 사용자 확인 대기) 완료.
T4(축제 feature)는 실험 완료 후 **미채택**. T10~T12는 제출 후. 결과는
[MODEL_SESSION_LOG_20260918.md](MODEL_SESSION_LOG_20260918.md)와 [MODEL_CARD.md](MODEL_CARD.md) 참조.

## ⏰ 마감 기준 3일 일정 (제출 2026-09-21, 오늘 09-18)

제출은 1차 기능심사용이고, 발표·심사는 그 뒤입니다. 따라서 3일 안에 (a) 제출본에서 모델이 확실히 돌아가고
(b) 심사·발표일까지 모델이 죽지 않게 하는 것이 목표이며, 그 외 개선은 "제출 후 발표 전" 구간으로 미룹니다.

| 날짜 | 반드시 | 되면 좋음 |
| --- | --- | --- |
| **09-18 (목)** | T1-a 새 방문자 자료 수집 시도(append-only) → 새 행이 있으면 **T2 v3 전향 평가 먼저** → T1-b 재학습·v4 채택 판정 | T3 모델 상태 endpoint |
| **09-19 (금)** | T5 지역별 신뢰도·혼잡 등급, T7 요인 라벨 병합, T8 모델 카드 | **T4 축제 feature v1.1 실험 시작**(학습·비교표까지. 서비스 연결은 채택 시에만) |
| **09-20 (토)** | T9 문서·PR 정리, 전체 테스트·빌드·E2E, 제출용 재현 절차 확인 | T4 채택 시 서비스 연결, T6 문체부 전년 실적 표시 |
| **09-21 (일)** | 제출. 새 코드 금지, 문서·수치 오타만 수정 | — |
| 제출 후~발표 전 | T1 재학습 반복(2주 간격), 새 날짜 전향 평가 갱신, T10~T12 | 발표 리허설·시연 녹화 |

- 09-18 수집에서 새 자료가 0건이면(공표 지연) T1-b·T2는 건너뛰고 09-19·09-20 항목을 앞당깁니다. 수집은 이후 매일 아침 재시도.
- T4는 하루 안에 학습·비교표까지 못 가면 "실험 기록만 남기고 미채택"으로 마감합니다. 절대 21일 당일에 연결하지 않습니다.
- 각 날 끝에 `pytest` 124+개 통과, 09-20에는 frontend 타입검사·빌드·Playwright까지 통과해야 합니다.

## 0. 현재 위치 한 줄 요약

- **Tier 1은 끝났습니다.** `regional-daily-1.0-3e0451e58b0c`(D-30 시군구 방문자-일 LightGBM)이 5개 채택 기준을 통과해
  `main`에 병합·서비스 연결됐고, 2026-09-18 로컬 테스트 124개가 통과합니다.
- **모델을 처음부터 다시 만들 필요는 없습니다.** 남은 일은 (1) 시연 날에도 모델이 살아 있게 하기,
  (2) "축제" 정보가 예측에 들어가게 하기, (3) 심사에서 방어 가능한 설명·근거 만들기, (4) 팀·문서 정리입니다.
- 축제별 관람객 수 모델(문체부 자료)과 동료의 v2 실험은 둘 다 기준 미달로 **미채택**입니다. 3일 안에는
  뒤로 두고, 조건이 맞으면 제출 후 재시도합니다(§3 표 참조).

## 1. 가장 급한 문제: 모델이 2026-10-14 이후 죽는다

`daily_service.py`는 두 가지 이유로 `unavailable`을 돌려줍니다.

1. 목표일마다 **목표일 − 60일까지의 이력**이 필요합니다. 현재 이력은 `data_end = 2026-08-15`이므로
   2026-10-14보다 늦게 시작하는 행사는 지금도 이미 예측이 안 됩니다.
2. `now − data_end > 60일`이면 모델 전체를 거부합니다. 즉 **2026-10-15부터 모든 예측이 사라집니다.**

따라서 새 방문자 자료를 받아 **재학습하는 절차를 스크립트 하나로 고정**하고, 발표 전까지 2~3주마다 반복해야 합니다.

## 2. 작업 목록 (우선순위 순)

| # | 작업 | 우선순위 | 규모 | 심사 항목 |
| --- | --- | --- | --- | --- |
| T1 | 방문자 이력 갱신 + 재학습 절차 고정 (v4 artifact) | **P0** | 중 | 구현성·안정성 |
| T2 | 동결된 v3 모델의 진짜 전향 평가 | **P0** | 소 | 데이터 근거·완성도 |
| T3 | 모델 상태 점검 endpoint/명령 (시연 전 확인용) | **P0** | 소 | 안정성 |
| T4 | TourAPI 축제 일정 feature 추가 실험 (v1.1) | **P1** | 대 | TourAPI 활용 20점·기획력 |
| T5 | 지역별 신뢰도·혼잡 등급을 데이터로 계산 | **P1** | 소 | 완성도 |
| T6 | 문체부 전년 실적을 "실제값 참고"로 표시 | **P1** | 중 | 데이터 활용·실용성 |
| T7 | 설명 계층 정리(SHAP 표기·요인 라벨 병합) | **P1** | 소 | 발전성 |
| T8 | 모델 카드 + 지역 규모별 오류 분석 문서 | **P1** | 소 | 발표 |
| T9 | PR #29·#30 정리, CLAUDE.md·MODEL_PLAN 동기화 | **P1** | 소 | 팀 |
| T10 | Windows 재현 점검 스크립트 | **P2** | 소 | 안정성 |
| T11 | 모델 artifact 포장·서버 전달 절차 | **P2** | 소 | 배포 |
| T12 | LLM 고정 제약 위반 방어 (eval 1건 실패) | **P2** | 소 | 완성도 |

P0는 반드시, P1은 시간이 허락하는 순서대로, P2는 팀 결정 후 진행합니다.

---

## T1. 방문자 이력 갱신 + 재학습 절차 고정 (P0)

**왜**: §1. 지금 절차는 `data/README.md`의 명령 5개를 손으로 이어 붙이고 검증 시작일을 사람이 정합니다.
실수하면 채택 조건을 통과 못 한 모델을 서비스에 물리거나, 기존 결과 폴더를 덮어쓸 수 있습니다.

**무엇을**
1. `backend/scripts/refresh_daily_forecast.py` 신설. 한 번 실행하면 다음을 순서대로 수행합니다.
   - `collect visitors`를 **append-only**로 호출해 `data/raw/visitors-<YYYYMM>-refresh-<날짜>.jsonl`에 저장
     (기존 파일은 절대 수정·삭제하지 않음. `completed_page`로 이어받기).
   - 새 파일까지 포함해 `build_daily_forecast_dataset` → `evaluate_daily_forecast` → `save_daily_run`.
   - 출력 폴더는 `data/processed/daily-forecast-production-v<N+1>/`로 **자동 증가**. 이미 있으면 중단.
   - 끝나면 `model_adopted`, 5개 adoption_checks, data_end, **마지막 예측 가능 목표일(data_end+60)** 을 한 줄로 출력.
2. **검증 분할 규칙을 코드에 고정**합니다(사람이 날짜를 고르지 않게):
   - `test_start` = data_end를 포함하는 달의 1일(그 달이 15일 미만이면 앞 달 1일).
   - `validation_start` = test_start − 2개월.
   - 이 규칙을 `forecasting.py`에 함수 `default_split_dates(data_end)`로 두고 테스트로 고정.
3. `HEUNGMAP_DAILY_MODEL_DIR`를 새 폴더로 바꾸는 건 **사람이 한다**(자동 교체 금지). 스크립트는
   바꿀 값을 출력만 합니다. `daily_service.DEFAULT_DIRECTORY`는 v3로 두지 말고 환경변수 필수로 바꾸는 것도
   검토하되, 로컬 개발 편의를 위해 "가장 번호가 큰 채택된 production-v*" 자동 선택으로 대체해도 됩니다.
   (선택: 후자를 권장. 단, 채택되지 않은 폴더는 건너뛰어야 함.)

**어디를**: `backend/scripts/refresh_daily_forecast.py`(신규), `backend/app/demand/forecasting.py`(분할 규칙),
`backend/app/demand/daily_service.py`(폴더 선택), `backend/tests/test_daily_forecast.py`, `data/README.md`,
`docs/MODEL_EVALUATION.md`.

**완료 조건**
- 새 v4 artifact가 만들어지고 5개 채택 조건 통과 여부가 기록됨. **통과 못 하면 v3 유지**하고 그 사실을 문서에 남김.
- 재학습 후 "마지막 예측 가능 목표일"이 발표 예정일 + 30일 이후임.
- 분할 규칙 단위 테스트, 폴더 자동 증가·덮어쓰기 금지 테스트 추가.

**검증**: `refresh` 실행 → `verify_demand_model.py --model-dir <v4>` → pytest → uvicorn 띄워 방문객 상세에서
10월 말 행사 예측이 `available`로 나오는지 확인.

**주의**: 한국관광공사 방문자 API가 8월 16일 이후 자료를 아직 공개하지 않았을 수 있습니다(공표 지연 가정 30일).
이 경우 스크립트는 "새 행 0건"을 출력하고 종료해야 하며, 재시도 날짜를 문서에 적습니다.

## T2. 동결된 v3 모델의 진짜 전향 평가 (P0, T1의 수집 직후·재학습 전에 실행)

**왜**: 현재 성능표는 "개발 중 이전 평가를 본 뒤의 후향 실험"이라고 스스로 밝히고 있습니다. 새로 받은
2026-08-16 이후 자료는 v3가 **한 번도 본 적 없는 미래**이므로, 여기서 v3를 그대로 채점하면 발표에서
"완전히 손대지 않은 전향 시험"이라고 말할 수 있습니다. 심사의 데이터 근거·완성도 항목에 직접 기여합니다.

**무엇을**
- `backend/scripts/evaluate_frozen_daily_model.py --model-dir data/processed/daily-forecast-production-v3 --history <새 raw 포함> --start 2026-08-16`
- v3의 `history.csv`가 아니라 **새 원본에서 다시 만든 이력**을 쓰되, 각 목표일에 대해 `목표일−60일`까지만
  잘라 feature를 만듭니다(서비스와 같은 `make_forecast_features` 재사용).
- 출력: 기준선 vs v3 결합의 WAPE·중앙APE·RMSLE·±20%·80%구간 포함률, 그리고 지역 규모 5분위별 표.
  `data/processed/daily-forecast-production-v3/forward-evaluation-<날짜>.json`으로 저장하고 manifest는 건드리지 않음.
- 결과가 후향 평가보다 나쁘더라도 **그대로 문서화**합니다. 좋게 보이도록 기간을 고르지 않습니다.

**완료 조건**: MODEL_EVALUATION.md에 "전향 평가(2026-08-16~data_end)" 절이 실제 수치와 함께 추가됨.

## T3. 모델 상태 점검 endpoint/명령 (P0)

**왜**: 시연 당일 모델이 조용히 `unavailable`로 떨어지는 사고를 막아야 합니다. 지금은 예측을 눌러 봐야 압니다.

**무엇을**
- `GET /api/system/model-status`(인증 불필요, 비밀값 없음): `model_version`, `data_end`, `created_at`,
  `last_predictable_target_date`(= data_end+60), `days_until_stale`(= 60 − (오늘 − data_end)), `regions`,
  `adopted: true/false`, 로드 실패 시 `reason`. 응답 schema를 `contracts/openapi.yaml`에 추가(공통 계약 변경이므로
  동료 검토 1회).
- `backend/scripts/verify_demand_model.py`에 같은 정보를 출력하도록 확장(이미 있는 스크립트 재사용).
- 프론트는 건드리지 않아도 됨(선택: 기획자 화면 하단에 "모델 버전·자료 기준일" 한 줄 — 동료 담당).

**완료 조건**: 테스트에서 artifact가 없을 때·노후일 때·정상일 때 세 경우 응답 확인.

## T4. TourAPI 축제 일정 feature 실험 — v1.1 (P1, 가장 큰 가치)

**왜**: 지금 모델은 **축제 정보를 전혀 쓰지 않습니다.** 지역 이력만 봅니다. 심사위원이 "축제 흥행 예측인데
축제가 입력에 없나?"라고 물으면 답이 없습니다. 반대로 TourAPI `searchFestival2` 일정을 feature로 넣으면
"TourAPI가 예측 모델 입력의 일부"라는 가장 강한 활용 근거가 생깁니다(배점 20점).

**설계 원칙(누수 방지)** — TourAPI 항목에는 `createdtime`이 있습니다. 예: 2026-07-29 시작 축제가 2026-07-21에
등록됨. 즉 D-30 시점에는 몰랐던 축제입니다. 따라서 **`createdtime ≤ 목표일 − 30일`인 축제만** feature에 씁니다.
(예측 시점에 실제로 알 수 있던 정보만 사용 — 원래 채택 조건과 같은 원칙.)

**feature 후보(3개로 제한)**
| feature | 정의 | 계산 시점 |
| --- | --- | --- |
| `festival_active` | 목표일에 해당 시군구에서 진행 중인 (D-30 이전 등록) 축제 수 | 목표일−30 |
| `festival_active_last_year` | 전년도 같은 요일 기준 3일 창에서 진행 중이던 축제 수 | 이력 |
| `festival_days_in_window` | 목표일 ±3일 안에 축제가 있는 날 수 | 목표일−30 |

시군구 매칭은 이미 있는 `KorService2 지역 필터 정규화`(PR #28)와 `ADMIN_TO_AREA`를 재사용. 2024~2026 축제 원본
(`data/raw/festivals-2024.jsonl`, `-2025.jsonl`, `-2026-jan-aug.jsonl`)이 있으므로 새 수집은 필요 없습니다.

**무엇을**
1. `forecasting.py`에 `FESTIVAL_FEATURES` 추가, `make_forecast_features(target, history, festivals=None)` 시그니처 확장.
   `festivals=None`이면 지금과 완전히 같은 결과(기존 테스트 유지).
2. `train_daily_forecast.py --festivals <jsonl...>` 옵션. 없으면 v1.0과 동일 학습.
3. 채택 판정은 **기존 5개 조건 + "축제 feature 없는 동일 설정보다 검증 WAPE가 좋을 것"** 1개를 더한 6개.
   통과 못 하면 **채택하지 않고 실험 결과만 문서화**합니다(v2 실험처럼 NO-GO도 기록 가치가 있음).
4. 서비스: `daily_service.predict_demand`가 TourAPI 축제 목록을 받아 같은 feature를 만들도록 하되,
   호출 실패 시 feature를 0으로 채우지 말고 `unavailable(upstream_unavailable)`을 반환합니다. (0으로 채우면
   학습 분포와 달라져 조용히 틀립니다.) 이미 있는 `services/cache.py`를 써서 축제 목록을 캐시합니다.
5. 요인 라벨 추가: `festival_active` → "같은 기간 지역 내 축제", 설명에 "TourAPI searchFestival2 기준" 명시.

**완료 조건**
- 축제 feature 유/무 두 학습의 검증·시험 성능 비교표가 MODEL_EVALUATION.md에 있음.
- 채택 시 model_version `regional-daily-1.1-…`, manifest `features`가 늘어나므로 `daily_service._load`의
  `manifest.features == FEATURES` 검사를 **manifest에 적힌 feature 목록을 그대로 신뢰해 모델·입력 순서를
  맞추는 방식**으로 바꿔 v1.0·v1.1 artifact를 둘 다 읽을 수 있게 함.
- 미채택 시 코드는 남기되 기본 경로는 v1.0 그대로.

**규모 주의**: 이 작업이 가장 큽니다. T1~T3를 끝내고 발표까지 2주 이상 남았을 때만 시작합니다.
PR #30의 `audit_tourapi_detail_features.py`는 여기서 재사용할 가치가 있으니 cherry-pick 후보입니다.

## T5. 지역별 신뢰도·혼잡 등급을 데이터로 계산 (P1, 작음)

**왜**: 지금 `confidence="medium"`은 **하드코딩**이고 `congestion_level="unknown"`입니다. 그런데 홀드아웃 오류는
지역 규모에 따라 크게 다릅니다(2026-09-18 v3 홀드아웃 재계산):

| 지역 방문자 규모 5분위 | 일평균 방문자 | WAPE | 중앙 APE |
| ---: | ---: | ---: | ---: |
| 하위 20% | 49,005 | 7.84% | 5.20% |
| 20~40% | 116,663 | 5.88% | 4.04% |
| 40~60% | 210,167 | 4.07% | 3.06% |
| 60~80% | 320,494 | 3.43% | 2.87% |
| 상위 20% | 594,151 | 3.18% | 2.50% |

오류 상위 지역: 영덕군 15.6%, 옹진군 15.1%, 무주군 14.5%, 남해군 14.1%, 단양군 14.0% — 전부 관광지형 군 지역.
큰 도시는 잘 맞고, 축제가 많은 작은 관광 지역일수록 틀립니다. 이걸 숨기지 말고 신뢰도에 반영합니다.

**무엇을**
1. `save_daily_run`이 홀드아웃 예측에서 **시군구별 WAPE**를 계산해 manifest `regions[].holdout_wape`에 저장.
2. `daily_service`가 confidence를 규칙으로 결정: WAPE < 5% → high, 5~10% → medium, ≥10% 또는 홀드아웃 표본
   < 10일 → low. 임계값은 manifest `confidence_thresholds`에 기록(코드 상수 아님).
3. `congestion_level`: 예측 p50의 일평균을 그 지역 **최근 365일 관측 분포의 백분위**로 환산.
   < 50% → low, 50~75 → medium, 75~90 → high, ≥ 90 → very_high. 라벨은 "평소 대비 지역 방문수요 수준"이며
   현장 혼잡이 아니라는 limitation 한 줄을 그대로 유지. `ticket_demand_level`은 계속 `unknown`(근거 없음).
4. 홀드아웃 지역별 표를 MODEL_EVALUATION.md에 넣습니다(T8과 합쳐도 됨).

**완료 조건**: 계약 변경 없음(둘 다 기존 enum). 테스트: 임계값 경계, 이력 부족 시 `unknown` 유지.

## T6. 문체부 전년 실적을 "실제값 참고"로 표시 (P1)

**왜**: 축제별 관람객 **모델**은 탈락했지만, 이미 수집한 문체부 자료 10,198행은 그 자체로 가치가 있습니다.
"이 축제의 전년도 보고 방문객 N명(계측/추정 구분)"을 **예측이 아니라 관측된 실제값**으로 보여 주면
기획자와 방문객 모두에게 즉시 유용하고, "관람객 수를 예측한다"는 과장 없이 축제 규모 감을 줍니다.

**무엇을**
1. `backend/app/attendance/data.py`의 정확 일치 매칭(지자체 + 회차·연도 제거 축제명)을 그대로 재사용해
   TourAPI 행사 → 문체부 행을 찾는 `lookup_previous_attendance(event) -> AttendanceRecord | None`.
   **퍼지 매칭 금지**(D30과 동일). 못 찾으면 None이고 화면에 아무것도 안 보임.
2. 결과는 Prediction이 아니라 `Evidence(value_type="verified_fact")`로 `evidence`에 추가.
   label "문체부 보고 전년 방문객", display_value "N명 (계측/추정/무응답)", source는 문체부 URL,
   limitation "주최 측이 문체부에 제출한 값이며 집계 방식이 축제마다 다릅니다."
3. 담당자 성명·연락처는 절대 읽지 않음(이미 파이프라인이 제외).
4. 가공 lookup 표는 `data/processed/mcst-attendance-lookup.csv`(Git 제외)로 만들고 checksum을 manifest에.

**완료 조건**: 매칭률(TourAPI 축제 중 몇 %가 문체부 행과 연결되는지)을 문서에 기록. 계약 변경 없음.

## T7. 설명 계층 정리 (P1, 작음)

- 지금 요인은 `pred_contrib=True`로 계산하는데, 이것이 **LightGBM 내장 TreeSHAP**입니다. 즉 Tier 2의 "SHAP 근거"는
  사실상 구현돼 있습니다. 문서·발표에 "TreeSHAP(pred_contrib) 기반 기여도"라고 정확히 적습니다.
  별도 `shap` 패키지 설치는 하지 않습니다.
- `month_sin`·`month_cos`가 둘 다 "계절"로 표시돼 요인 목록에 같은 라벨이 두 번 나올 수 있습니다.
  같은 라벨 요인은 기여도를 합쳐 하나로 보여 주도록 `daily_service`에서 병합.
- 요인 설명의 "인과효과는 아닙니다" 문구는 유지.

## T8. 모델 카드 + 오류 분석 문서 (P1, 작음)

발표·심사용 한 장짜리 `docs/MODEL_CARD.md`: 목적, 입력(무엇을 쓰고 무엇을 안 쓰는지), 학습 자료 기간,
분할 방법, 후향·전향(T2) 성능, 지역 규모별 오류(T5 표), 한계, 재학습 주기, 버전 이력(1.0 → 1.1).
수치는 전부 evaluation.json에서 가져오고 "정확도 96%" 같은 표현은 쓰지 않습니다.

## T9. PR·문서 정리 (P1, 작음, 사람 결정 필요)

- **PR #29**(동료): "수요 모델 = 박지성, LLM = 홍성주"로 적혀 있으나 **모델 담당은 홍성주가 맞습니다(2026-09-18 확인).**
  #29를 닫고 `TEAM_WORKFLOW.md` 역할표에 "AI 수요 모델·예측 계약: 홍성주"를 추가합니다. 닫기 전에 팀원에게 한 줄 알립니다.
- **PR #30**(동료 v2 실험, NO-GO): 결론이 이미 기록됐으므로 닫고, `audit_tourapi_detail_features.py`만
  T4 브랜치로 cherry-pick. 닫을 때 코멘트에 "NO-GO 기록은 DATA_GATE_REPORT에 보존, 감사 도구는 T4에서 재사용" 명시.
- `CLAUDE.md`의 "지금 상태" 칸이 "API 키 발급 단계"로 남아 있음 → 현재 상태(모델 채택·연결 완료, 이 문서 링크)로 갱신.
- `MODEL_PLAN.md`의 "권장 모델 구조"는 실제와 다른 uplift 모델을 그림으로 그리고 있음 → "계획(미구현)"임을
  상단에 명시하거나 실제 구조(기준선 + 잔차 보정)로 교체.

## T10. Windows 재현 점검 (P2)

학습은 이미 `random_state=42, deterministic=True, n_jobs=1, force_col_wise=True`라 결정적입니다.
`backend/scripts/reproduce_check.py`: `backend/tests/fixtures`의 작은 합성 이력으로 학습 후 metric을
`fixtures/expected-metrics.json`과 소수점 4자리까지 비교. Mac에서 기대값을 만들고 동료가 Windows에서 실행.
pandas 3.0.5 / lightgbm 4.7.0 핀은 그대로 유지.

## T11. 모델 artifact 포장·서버 전달 (P2, 배포 결정 후)

`backend/scripts/package_model.py --model-dir <v4> --output dist/model-<version>.tar.gz`: 폴더를 묶고
전체 sha256을 출력. 서버에서는 풀고 `HEUNGMAP_DAILY_MODEL_DIR`만 설정. D20에서 배포는 현재 범위 밖이므로
발표 방식(로컬 시연 vs 서버)이 정해진 뒤 진행. 시연이 로컬이면 이 작업은 생략 가능.

## T12. LLM 고정 제약 위반 방어 (P2)

`llm-eval-final-v3.json`: 5개 시나리오 중 `contradictory_capacity`만 실패("LLM 응답이 입력된 고정 제약을 위반").
LLM 재프롬프트로 고치려 하지 말고, **코드에서 응답을 검증해 고정 제약과 어긋나면 해당 추천을 버리고
`limitations`에 "일부 추천은 제약 검증에서 제외됨"을 추가**하는 결정론적 방어를 넣습니다.
LLM 담당이 누구인지 T9 합의에 따릅니다(PR #29 기준이면 홍성주).

---

## 3. 보류·조건부 항목 (원칙 아님, 시간 대비 기대값 판단)

사용자 결정: "하지 않기로 한 것도 할 수 있거나 하는 게 좋으면 해도 된다." 따라서 아래는 금지 목록이 아니라
**지금 순서에서 뒤에 있는 이유**와 **하려면 어떤 조건에서 하는지**를 적은 표입니다.

| 항목 | 지금 뒤로 미는 이유 | 하려면 이 조건에서 |
| --- | --- | --- |
| 모델 처음부터 재설계 | 현재 모델이 5개 채택 기준을 통과. 문제는 성능이 아니라 노후화·축제 정보 부재·설명 | 발표 전 재학습(T1)이 채택 실패할 때만 기준선 구조를 다시 봄 |
| 문체부 축제별 관람객 **모델** 재시도 | 이미 학습해 봤고 중앙 APE가 "전년도 값 그대로"보다 나쁨(18.0→20.3%). 3일 안에 뒤집을 새 feature가 없음 | T4 축제 feature가 채택되면, 같은 feature를 관람객 모델에 넣어 제출 후 재시도. 채택 기준(전년값 대비 중앙 APE 개선)은 유지 |
| 문체부 자료 자체 | 가치 있음 → **T6로 승격**. 예측이 아니라 "전년 보고 실적(실제값)"으로 표시 | 09-20 되면 좋음 항목 |
| 동료 v2 실험(PR #30) 부활 | 최종 구간에서 기준선보다 8.59% 나쁨으로 NO-GO 판정 완료 | 감사 도구만 T4에 cherry-pick. 모델 자체는 재시도 근거 없음 |
| 날씨 feature | D-30 시점에 행사 당일 날씨를 알 수 없음. 과거 날씨를 넣어도 예측 시점엔 못 만듦 → 누수 | 기후 평년값(월별 평균)이라면 가능하지만 이미 `month_sin/cos`가 같은 정보를 담음. 기대값 낮음 |
| 예산·출연진 feature | 예측 시점 확보·재현 불가, 표본 없음 | 문체부 예산 열은 있음. 축제별 관람객 모델 재시도 시 후보로만 |
| 티켓 수요 등급 | 근거 데이터가 없음 | 예매 데이터 확보 전까지 `unknown`. "티켓팅 경쟁도" 표현으로 바꾸는 것은 D7·DECISION_LOG 결정과 충돌하므로 팀 합의 필요 |
| 퍼지 매칭·결측 0 채우기·미채택 모델 자동 연결 | 조용히 틀리게 만드는 방식이라 심사에서 방어 불가 | 하지 않음 (유일한 고정 원칙) |
| "정확도 96%" 표현 | 심사 기준 "한계를 숨기지 않는다"와 충돌 | 하지 않음. "D-30 시군구 방문자-일 WAPE 3.8%(시간 홀드아웃)"로 표현 |

## 4. 사람이 정해야 하는 것 (코드로 못 정함)

1. ~~제출 날짜~~ → **2026-09-21 확정.** 발표·최종심사 날짜는 아직 미확인 — 그 날짜 + 30일까지 예측 가능하도록 T1 재학습 주기를 정해야 합니다.
2. PR #29 역할표 — **모델 담당은 홍성주로 확정(사용자 확인).** #29의 "수요 모델 = 박지성" 기술은 현실과 다르므로 팀원에게 알리고 닫습니다.
3. 시연 방식(로컬 vs 서버) — T11 필요 여부.
4. LLM 담당 — T12 소유자.

## 5. Opus 실행 순서 요약

```text
[09-18] T1 수집(append-only) ──▶ T2 v3 전향 평가(재학습 전!) ──▶ T1 재학습·v4 채택 판정 ──▶ T3 상태 endpoint
[09-19] T5 신뢰도·혼잡 ──▶ T7 설명 정리 ──▶ T8 모델 카드 ──▶ T4 축제 feature 학습·비교표
[09-20] T9 PR·문서 ──▶ 전체 검증 ──▶ (채택 시) T4 서비스 연결 ──▶ T6 문체부 실제값
[09-21] 제출
[제출 후] T1 반복, T10~T12, 발표 준비
```

각 작업은 별도 브랜치·PR(`feat/model-refresh`, `feat/model-forward-eval`, …)로 올리고, 원본·가공 데이터·artifact·
`.env`는 계속 커밋하지 않습니다.
