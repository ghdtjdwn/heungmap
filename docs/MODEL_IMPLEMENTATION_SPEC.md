# 모델 담당 구현 명세 (Opus 실행용) — 2026-09-18

[MODEL_WORK_PLAN.md](MODEL_WORK_PLAN.md)의 T1~T12를 **한 세션에서 순서대로 전부 구현**하기 위한 명세입니다.
"왜"는 WORK_PLAN에 있고, 이 문서는 **무엇을 어디에 어떻게** 만 적습니다. 판단이 필요한 지점은 미리 결정해 뒀고,
결정할 수 없는 지점은 `[STOP]`으로 표시했으니 그때만 사용자에게 묻습니다.

## 실행 규칙

1. 시작 전 읽기: `AGENTS.md`, 이 문서, `docs/MODEL_WORK_PLAN.md`, `docs/MODEL_EVALUATION.md`.
2. 작업 단위 = 아래 Step. **각 Step 끝에 `PYTHONPATH=backend .venv/bin/pytest -q backend/tests`가 통과해야** 다음 Step으로.
   실패하면 고치고 넘어가되, 30분 넘게 막히면 그 Step을 `[SKIPPED: 이유]`로 기록하고 다음으로.
3. 브랜치: `feat/model-submission-20260921` 하나. Step마다 commit(메시지는 아래 지정). 마지막에 PR 하나. push·PR 생성 전에 사용자에게 확인.
4. 절대 커밋 금지: `data/raw/*`, `data/processed/*`, `.env`, `*.sqlite3`, `frontend/next-env.d.ts` 변경.
5. 기존 artifact 폴더(`daily-forecast-production-v3` 등)는 **읽기만**. 새 폴더는 항상 `exist_ok=False`.
6. 코드 스타일: 기존 파일과 같은 밀도(한국어 docstring 한 줄, 타입 힌트, 긴 한 줄 허용). 새 의존성 추가 금지(`shap` 포함).
7. 숫자 표현: 문서·코드 문자열에 "정확도 N%" 금지. "WAPE", "중앙 절대비율오차", "±20% 이내 비율"만 사용.
8. 진행 로그: `docs/MODEL_SESSION_LOG_20260918.md`에 Step별 결과(명령, 핵심 수치, 커밋 해시)를 append. 마지막에 NEXT_SESSION_COMMAND.md 갱신.

## 사전 확인된 사실 (다시 조사하지 말 것)

- 채택 artifact: `data/processed/daily-forecast-production-v3/` — `data_end=2026-08-15`, 264 시군구, model_weight 0.4,
  calibration ±0.06997, features 17개(`forecasting.FEATURES`).
- 방문자 API 공표 지연 실측: 2026-09-15 수집 시 최신 자료가 08-15 → **약 31일 지연**. 오늘(09-18) 수집하면 08-16~08-18쯤까지만 새로 나올 가능성이 큼.
- `verify_demand_model.py`는 **옛 모델(`demand/service.py`, D29 행사 단위)** 검증용이라 daily 모델에 못 씀. Step 3에서 daily용을 새로 만든다.
- 테스트는 `conftest.py`가 `HEUNGMAP_DEMAND_MODE=mock`을 강제하므로 API 테스트는 mock 경로. daily 모델 테스트는 `test_daily_service.py`의 `artifact` fixture(합성 이력 → `save_daily_run`)를 재사용한다.
- 계약 검사 `test_openapi_contract.py::test_implemented_paths_exist_in_approved_contract`는 **구현된 모든 경로가 `contracts/openapi.yaml`에 있어야** 통과. 새 endpoint는 계약 먼저.
- 요인 계산 `pred_contrib=True`는 LightGBM 내장 TreeSHAP. 별도 shap 패키지 불필요.
- 프론트는 `indicators.congestion_level`을 타입에만 갖고 있고 **표시하지 않음**(`frontend/lib/types.ts:208`). 신뢰도는 표시함.
- 축제 원본 `data/raw/festivals-{2024,2025,2026-jan-aug}.jsonl` 각 1줄(=1페이지 파일이 아니라 JSONL 한 줄에 페이지 하나). `normalize_festivals`가 `region_code`(5자리 법정동 시군구)와 `start_date/end_date`(YYYYMMDD)를 만든다. 원본 item에는 `createdtime`(YYYYMMDDHHMMSS)이 있으나 normalize가 **버림** → Step 6에서 보존하도록 확장.
- TourAPI 시군구 매칭 규칙은 `data_gate/pipeline.py::normalize_festivals` + `TOUR_AREA_TO_ADMIN`을 그대로 쓴다. 새 매핑표 만들지 않음.

---

## Step 0. 준비 (5분) — commit 없음

```bash
git checkout main && git pull && git checkout -b feat/model-submission-20260921
ls data/processed/daily-forecast-production-v3/   # 6개 파일 확인
PYTHONPATH=backend .venv/bin/pytest -q backend/tests   # 124 passed 기대
```
`docs/MODEL_SESSION_LOG_20260918.md` 생성, 상단에 시작 시각·테스트 결과 기록.

---

## Step 1. 방문자 자료 수집 (T1-a) — `data: 2026-08-16 이후 방문자 원본 append 수집` (raw는 커밋 안 함, 로그만)

```bash
PYTHONPATH=backend .venv/bin/python -m app.data_gate.cli collect visitors \
  --start 20260816 --end 20260930 --rows 10000 --max-pages 10 \
  --output data/raw/visitors-2026-aug-sep-refresh-20260918.jsonl
```
- 기존 파일에 절대 쓰지 않는다(새 파일명). 실행 후 아래로 새 자료 범위를 확인해 로그에 적는다.
```bash
python3 -c "
import json;mx=mn=None;n=0
for l in open('data/raw/visitors-2026-aug-sep-refresh-20260918.jsonl'):
    p=json.loads(l);n+=len(p['items'])
    for i in p['items']: d=i['baseYmd'];mx=max(mx or d,d);mn=min(mn or d,d)
print(n,mn,mx)"
```
- **분기**: 새 날짜(08-16 이후)가 `0일` → Step 2·4 건너뛰고 Step 3부터. 로그에 "공표 지연으로 새 자료 없음, 재시도 09-19 오전" 기록.
  새 날짜가 `1일 이상` → Step 2로. (단 며칠이라도 전향 평가 가치가 있다.)

---

## Step 2. 동결 v3 전향 평가 (T2) — `feat(model): 동결 모델 전향 평가 스크립트`

**신규** `backend/scripts/evaluate_frozen_daily_model.py`

```python
"""채택된 일별 모델을 학습에 쓰지 않은 새 관측일에 그대로 채점한다. 모델·manifest를 수정하지 않는다."""
# 인자: --model-dir (기본 daily_service.DEFAULT_DIRECTORY), --visitors <jsonl...> (전체 원본, 새 파일 포함),
#       --start YYYY-MM-DD (기본: manifest data_end + 1일), --output <json 경로>
#       (기본: <model-dir>/forward-evaluation-<YYYYMMDD>.json ; 이미 있으면 에러)
```
알고리즘:
1. `daily_service._artifact()`로 manifest·models 로드(무결성 검사 재사용). `HEUNGMAP_DAILY_MODEL_DIR`를 `--model-dir`로 설정 후 호출.
2. `load_daily_visitors(args.visitors)` → `daily`. 평가 대상 = `daily[daily.date >= start]` 중 manifest `regions`에 있는 시군구.
3. 각 (region, date)에 대해 `make_forecast_features(date, history_of_region)` — history는 **전체 daily**(함수 내부가 이미 목표일−60일까지만 참조하므로 미래 누수 없음. 단 `retrieved_at` 필터는 불필요).
   `InsufficientForecastHistory`면 건너뛰고 카운트.
4. p50 = `expm1(log1p(baseline) + model_p50.predict(x) * model_weight)`, 구간 = center_log ± calibration quantile (daily_service와 동일 수식. **daily_service의 예측 코드를 함수로 추출해 공유**: `daily_service.predict_rows(models, manifest, frame_of_features, baselines) -> (low, center, high)` 를 만들고 `predict_demand`도 그것을 쓰게 리팩터. 기존 테스트로 회귀 확인.)
5. `forecasting.metrics(actual, p50)`, `metrics(actual, baseline)`, 80% 구간 포함률, 그리고 지역 규모 5분위(`pd.qcut(actual,5)`)별 `{n, mean_actual, wape, median_ape}`, 시군구별 wape 상위 10.
6. JSON 저장: `{schema_version:"1.0", model_version, evaluated_at, period:{start,end}, rows, skipped_rows, model, seasonal_growth_baseline, wape_improvement, interval_80_coverage, by_size_quintile:[...], worst_regions:[...], note:"학습·후보선택에 쓰지 않은 관측일에 대한 전향 평가"}`.
7. stdout에 같은 JSON 출력. 종료 코드 0(평가 완료; 채택 판정 아님).

테스트 `backend/tests/test_frozen_evaluation.py`: `test_daily_service.artifact` fixture + 합성 이력을 2026-08-16~08-31로 연장한 daily → 스크립트의 핵심 함수(`evaluate_frozen(manifest, models, daily, start)`)를 직접 호출해 rows>0, 키 존재, `wape>=0`, manifest 파일 mtime 불변 확인. (스크립트 본체는 `main()`과 `evaluate_frozen()`으로 분리.)

문서: `docs/MODEL_EVALUATION.md` "관측 성능" 아래에 `## 전향 평가 (2026-08-16~<end>)` 절 추가 — 표(기준선 vs 모델), 행 수, "표본이 N일로 작다"는 한계 명시. 수치는 JSON에서 복사.

---

## Step 3. daily 모델 검증 스크립트 + 상태 endpoint (T3) — `feat(model): 일별 모델 상태 점검 endpoint`

### 3-a `backend/app/demand/daily_service.py`에 추가
```python
def model_status(now: datetime | None = None) -> dict:
    """artifact를 검증해 로드하고 노후 여부를 계산한다. 비밀값·경로를 노출하지 않는다."""
    # 반환: {"status": "ready"|"stale"|"unavailable", "model_version", "data_end", "created_at",
    #        "last_predictable_target_date": data_end+60, "days_until_stale": 60-(today-data_end),
    #        "regions": len, "adopted": bool, "reason": str|None}
    # unavailable: _artifact() 예외(OSError, ValueError, KeyError, TypeError, ImportError) → reason은 예외 메시지(경로 미포함)
    # stale: today - data_end > 60 (predict_demand와 같은 조건)
```
### 3-b `backend/app/schemas.py`에 `ModelStatusResponse(ContractModel)` — 위 필드. `status: Literal["ready","stale","unavailable"]`, 날짜는 `date | None`, `created_at: datetime | None`, `reason: str | None`.
### 3-c `contracts/openapi.yaml`: `paths./system/model-status` (GET, operationId `getModelStatus`, tags [system]) + `components.schemas.ModelStatusResponse`. `/health` 항목 바로 아래에 둔다. `test_openapi_contract.py`의 schema 목록에 `ModelStatusResponse` 추가.
### 3-d `backend/app/main.py`: `/health` 아래에
```python
@app.get("/api/v1/system/model-status", response_model=ModelStatusResponse, response_model_exclude_none=True,
         operation_id="getModelStatus", tags=["system"])
def get_model_status() -> ModelStatusResponse:
    from app.demand.daily_service import model_status
    return ModelStatusResponse(**model_status())
```
### 3-e **신규** `backend/scripts/verify_daily_model.py` (기존 `verify_demand_model.py`는 건드리지 않음)
- 인자 `--model-dir`, `--source-dir data/raw`. 순서: `model_status()` 출력 → manifest `source_files` checksum 대조 → `holdout-predictions.csv`의 (region, date)에 대해 `history.csv`로 `make_forecast_features` + `predict_rows` 재계산해 p50 `assert_allclose(atol=1e-6)` (round-trip) → `prediction_regions()` 전 지역에 대해 `now+7일~+9일` 온라인 예측 실행, available/unavailable 개수·평균 시간 출력. 종료 코드 0/1.
- README·MODEL_EVALUATION의 "바로 확인하기"에 이 명령 추가.

테스트 `backend/tests/test_daily_service.py`에 추가: `test_model_status_ready_stale_unavailable` — fixture로 ready; `as_of`를 2026-11-01로 주면 stale; `HEUNGMAP_DAILY_MODEL_DIR`를 빈 tmp로 바꾸면 unavailable + reason 문자열에 tmp 경로가 **포함되지 않음**. `test_main`/`test_events_api` 스타일로 `GET /api/v1/system/model-status`가 200과 `status` 필드 반환(mock 모드에서도 artifact 없으면 unavailable로 200).

---

## Step 4. 재학습 절차 고정 + v4 (T1-b) — `feat(model): 재학습 절차 고정과 분할 규칙`

### 4-a `backend/app/demand/forecasting.py`
```python
def default_split_dates(data_end) -> tuple[str, str]:
    """data_end가 속한 달(15일 미만이면 앞 달)의 1일을 test_start, 그 2개월 전 1일을 validation_start로 반환."""
    # 2026-08-15 → ("2026-06-01","2026-08-01")  ← 현재 v3와 동일
    # 2026-09-10 → ("2026-06-01","2026-08-01")  (9월이 15일 미만 → 8월)
    # 2026-09-20 → ("2026-07-01","2026-09-01")
```
`evaluate_daily_forecast`의 기본 인자는 그대로 두되 `train_daily_forecast.py`가 `--validation-start/--test-start` 미지정 시 `default_split_dates(daily.date.max())`를 쓰도록.

### 4-b **신규** `backend/scripts/refresh_daily_forecast.py`
- 인자: `--visitors <jsonl...>`(기본: `data/raw/visitors-*.jsonl` 중 `visitors.jsonl`·`visitors-2025.jsonl`(중복 구버전) 제외한 glob을 **명시 목록**으로 하드코딩: `visitors-2025-full`, `visitors-2026-jan-aug`, `visitors-2026-aug-refresh-20260915`, `visitors-2026-aug-sep-refresh-20260918` + 이후 추가분), `--output-root data/processed`(기본), `--no-collect`.
- 순서: (1) `--no-collect`가 아니면 Step 1 수집 명령을 오늘 날짜 파일명으로 실행(이미 있으면 이어받기) (2) `output = output_root / f"daily-forecast-production-v{N+1}"` — 기존 `production-v*` 최대 번호+1, **존재하면 즉시 에러** (3) `train_daily_forecast.main()` 로직 재사용(함수로 분리해 import) (4) 결과 한 줄: `{"output","model_adopted","checks","data_end","last_predictable_target_date","set_env":"HEUNGMAP_DAILY_MODEL_DIR=<abs>"}` (5) 종료 코드: 채택 0, 미채택 2.
- **환경변수 자동 교체 금지.** 출력만.

### 4-c `daily_service._directory()` 변경: 환경변수 없으면 `data/processed/daily-forecast-production-v*` 중 **번호가 가장 큰 폴더부터** manifest `model_adopted==True`인 첫 폴더. 없으면 기존 DEFAULT(v3). 이 선택 로직은 `select_production_directory(root) -> Path | None`으로 분리·테스트(tmp에 v3 채택, v4 미채택, v5 채택 만들면 v5 선택; v5 미채택이면 v3).

### 4-d 실행(Step 1에서 새 자료가 있을 때만)
```bash
PYTHONPATH=backend .venv/bin/python backend/scripts/refresh_daily_forecast.py --no-collect
PYTHONPATH=backend .venv/bin/python backend/scripts/verify_daily_model.py --model-dir data/processed/daily-forecast-production-v4
```
- 채택되면 `.env`에 `HEUNGMAP_DAILY_MODEL_DIR` 주석 유지(자동 선택이 v4를 잡음). MODEL_EVALUATION.md 상단 "현재 서비스 기본 모델"을 v4 버전·data_end·성능표로 갱신하고 v3 표는 "이전 버전" 절로 내림.
- 미채택이면 v3 유지, 미채택 이유(`rejection_reasons`)를 MODEL_EVALUATION.md에 기록. **v4 폴더는 삭제하지 않음.**

테스트: `test_daily_forecast.py`에 `default_split_dates` 3케이스; `test_daily_service.py`에 `select_production_directory` 케이스.

---

## Step 5. 지역별 신뢰도·혼잡 등급 (T5) — `feat(model): 홀드아웃 기반 지역별 신뢰도와 혼잡 등급`

### 5-a `forecasting.save_daily_run`: manifest `regions[]` 각 항목에 `holdout_wape`(그 지역 holdout 행의 |p50−target|합/target합, 행 없으면 null)와 `holdout_days` 추가. manifest에 `confidence_thresholds: {"high_below": 0.05, "medium_below": 0.10, "min_holdout_days": 10}` 와 `congestion_percentiles: {"medium": 50, "high": 75, "very_high": 90}` 추가. **schema_version은 "1.0" 유지**(하위 호환: 키 없으면 기존 동작). 호출부 시그니처 변경 없음(`predictions`에서 계산).
### 5-b `daily_service.predict_demand`:
- confidence: `region_meta = manifest regions[code]`; `holdout_wape`가 없거나 `holdout_days < min_holdout_days` → `"low"`; `< high_below` → `"high"`; `< medium_below` → `"medium"`; 그 외 `"low"`. **v3 manifest(키 없음)에서는 기존처럼 "medium"** 유지.
- congestion_level: `recent = history[history.date > cutoff-365 & date <= cutoff]` (cutoff = end_date−60). `len(recent) < 300`이면 `"unknown"`. 아니면 `daily_center.mean()`의 `recent.visitor_count` 백분위 → 등급. `ticket_demand_level`은 `"unknown"` 고정.
- factor/limitations에 한 줄 추가: `"혼잡 등급은 최근 1년 지역 방문자 분포에서 예측 일평균의 위치이며 현장 혼잡이 아닙니다."` (unknown이면 생략).
- `evidence`에 `ev_daily_region_holdout`(value_type `derived_value`, label "이 시군구 홀드아웃 오차", display_value `f"WAPE {wape:.1%} ({days}일)"`) — 값 있을 때만.
### 5-c 테스트: fixture manifest에 thresholds 주입해 high/medium/low 경계 3케이스, 이력 300일 미만 → unknown, v3형 manifest(키 없음) → "medium"·"unknown" 유지.
### 5-d 문서: MODEL_EVALUATION.md에 "지역 규모별 오류" 표(WORK_PLAN T5 표 재사용, 출처는 `holdout-predictions.csv` 재계산) + 신뢰도·혼잡 규칙 설명.
### 5-e (선택, 프론트 담당 영역이므로 **10줄 이내**만) `frontend/components/planner-result.tsx`·`visitor-event-detail.tsx`에서 `prediction.indicators?.congestion_level`이 `unknown`이 아닐 때 "평소 대비 지역 방문수요: 높음" 한 줄 표시. 라벨 맵 `{low:"낮음",medium:"보통",high:"높음",very_high:"매우 높음"}`. 프론트 `npm run lint && npx tsc --noEmit` 통과 확인. 막히면 skip.

---

## Step 6. 축제 feature v1.1 실험 (T4) — `feat(model): TourAPI 축제 일정 feature 실험`

**시간 상자: 이 Step은 최대 4시간.** 넘기면 실험 결과만 기록하고 미채택으로 마감.

### 6-a 축제 원본 로더 — **신규** `backend/app/demand/festivals.py`
```python
FESTIVAL_FEATURES = ["festival_active", "festival_active_last_year", "festival_days_in_window"]
def load_festival_calendar(paths) -> pd.DataFrame:
    """jsonl 페이지들을 normalize_festivals로 정규화하되 createdtime을 보존한다. 열: event_id, region_code, start, end, created(Timestamp)."""
    # normalize_festivals는 createdtime을 버리므로, 정규화 전에 item["createdtime"]을 별도 dict로 보관 후 event_id로 다시 붙인다.
    # created 없는 행은 제외하고 개수 기록. region_code가 5자리 아닌 행 제외.
def festival_features(target, region_code, calendar, known_by) -> dict[str, float]:
    """known_by(=target-30일) 이전에 등록된 축제만 사용. 누수 방지의 핵심."""
    # active = calendar[(region==code)&(created<=known_by)&(start<=target)&(end>=target)]
    # festival_active = len(active)
    # 전년: target-364 ±1일 창에서 진행 중이던 축제 수 (created 조건 없음: 이미 지난 일이므로 알 수 있음)
    # festival_days_in_window = target±3일 중 active 축제가 하나라도 있는 날 수 (0~7)
```
### 6-b `forecasting.py`
- `make_forecast_features(target_date, history, festival_calendar=None)`: None이면 현 동작. 있으면 `inputs.update(festival_features(...))`.
- `FEATURES`는 그대로; `feature_list(with_festivals: bool)` 헬퍼 추가. `_fit/_predict/build_daily_forecast_dataset/evaluate_daily_forecast`에 `features: list[str]` 인자(기본 FEATURES) 전달. `build_daily_forecast_dataset(daily, festival_calendar=None)`이 있으면 행마다 festival_features 열 추가(벡터화: region별 calendar를 미리 필터한 뒤 날짜 루프. 37k행이면 충분).
- `evaluate_daily_forecast(..., features=FEATURES, ablation_features=None)`: `ablation_features`가 주어지면 **같은 분할·같은 후보로 축제 feature 없는 학습을 한 번 더** 돌려 report에 `ablation: {"without_festival": {...validation wape, test wape}}`와 채택 조건 6번째 `beats_no_festival_validation_wape` 추가. v1.1의 `model_adopted`는 6개 모두.
- `save_daily_run`: manifest `features`에 실제 목록 저장(v1.1은 20개). `report["model_version"] = "regional-daily-1.1"`은 features가 확장됐을 때.
### 6-c `daily_service._load`: `manifest.features != FEATURES` 검사를 → `set(manifest.features) ⊆ set(FEATURES + FESTIVAL_FEATURES)` and `model.feature_name() == manifest.features`로 완화. `predict_demand(..., festival_calendar=None)`: manifest.features에 FESTIVAL_FEATURES가 포함되면 **calendar 필수**; 없으면 `_unavailable("upstream_unavailable", "축제 일정을 불러오지 못해 예측을 만들지 않습니다.")`. 0 채우기 금지.
- 호출부(`planner.build_analysis`, `events.build_event_prediction`): manifest가 축제 feature를 요구할 때만 `tourapi.search_festivals(start=target-60, end=end_date+7, area_code=region.area_code)`로 목록을 받아 `load_festival_calendar`와 같은 형태의 DataFrame으로 변환(`_festival_to_summary` 말고 raw item이 필요하므로 `TourApiClient.festival_items_raw(...)` 메서드 추가, `_festival_items` 래핑). `services/cache.py`의 `TtlCache`(ttl 300초) 인스턴스를 `daily_service` 모듈 수준에 하나 두고 key `f"{area_code}:{start}:{end}"`로 사용. 필요 여부는 `daily_service.requires_festival_calendar() -> bool`로 노출.
### 6-d 학습·비교
```bash
PYTHONPATH=backend .venv/bin/python backend/scripts/train_daily_forecast.py \
  --festivals data/raw/festivals-2024.jsonl data/raw/festivals-2025.jsonl data/raw/festivals-2026-jan-aug.jsonl \
  --output-dir data/processed/daily-forecast-festival-v1.1-experiment
```
(`train_daily_forecast.py`에 `--festivals` 옵션 추가; visitors 기본 목록은 Step 4-b와 동일 함수 사용.)
- 결과 표(검증·시험 각 WAPE/중앙APE/RMSLE, 축제 유/무)를 MODEL_EVALUATION.md `## 축제 일정 feature 실험 (v1.1)`에 기록. 축제 feature의 SHAP 평균 |기여|도 기록.
- **채택(6/6 통과) 시**: `daily-forecast-production-v<N+1>`로 재실행(실험 폴더 복사 금지, 재학습), 6-c 호출부 연결, `FEATURE_LABELS`에 `festival_active:"같은 기간 지역 내 TourAPI 등록 축제"`, `festival_active_last_year:"전년 같은 시기 지역 축제"`, `festival_days_in_window:"행사 전후 축제 밀집"` 추가, 소스에 `SourceRef(source_type="tourapi", dataset_name="searchFestival2 축제 일정(예측 입력)")` 추가. E2E·프론트 빌드 재확인.
- **미채택 시**: 코드는 유지(옵션 경로), 기본 학습은 v1.0. 문서에 NO-GO 수치 기록. DECISION_LOG에 D31로 기록(채택/미채택 모두).
### 6-e 테스트 `backend/tests/test_festival_features.py`: (1) `created > known_by` 축제는 무시됨(누수 차단) (2) 진행 중 축제 수 계산 (3) `festival_calendar=None`일 때 기존 17개 feature와 동일 결과 (4) manifest가 축제 feature 요구 + calendar None → `upstream_unavailable`.

---

## Step 7. 문체부 전년 실적 표시 (T6) — `feat(model): 문체부 보고 전년 방문객을 실제값 근거로 표시`

### 7-a **신규** `backend/app/attendance/lookup.py`
```python
def build_lookup(archives: Iterable[Path], output: Path) -> dict:  # data/processed/mcst-attendance-lookup.csv (Git 제외)
    # load_archives → 열: plan_year, province, district, title_key, title, prior_attendance, measurement
    # prior_attendance 양수 행만. 같은 (province, district, title_key)에 여러 연도면 plan_year 최대 행.
    # 담당자 성명·연락처 열은 load_archives가 이미 안 읽음 — 확인만.
def lookup_previous_attendance(*, title: str, region: RegionRef, table: pd.DataFrame) -> dict | None:
    # key = canonical_title(title)
    # province = ADMIN_TO_PROVINCE[region.legal_dong_code[:2]]  (없으면 None 반환)
    # district = normalize_district(region.display_name.split()[-1])  ("종로구" 또는 "서울 마포구" 둘 다 마지막 토큰)
    # 정확 일치 1건만 반환. 2건 이상 → None(모호). 퍼지 금지.
```
- **주의**: 모델 manifest의 지역 이름은 `"종로구"`처럼 광역 없이 시군구만 있고, TourAPI 행사의 `display_name`은 `"서울 마포구"`형이다. 그래서 광역은 이름이 아니라 **법정동 코드 앞 2자리**로 정한다. `lookup.py`에 상수 추가:
  `ADMIN_TO_PROVINCE = {"11":"서울","26":"부산","27":"대구","28":"인천","29":"광주","30":"대전","31":"울산","36":"세종","41":"경기","42":"강원","51":"강원","43":"충북","44":"충남","45":"전북","52":"전북","46":"전남","47":"경북","48":"경남","50":"제주"}`. `legal_dong_code`가 없으면 None.
### 7-b 연결: `planner.build_analysis`와 `events.build_event_prediction`에서 예측 결과가 `AvailablePrediction`이면 그 `evidence`·`sources`에, planner는 예측 상태와 무관하게 `PlannerAnalysisResponse.evidence`에도 추가한다. `EventDetail`에는 evidence 필드가 없으므로 방문객 쪽은 **예측이 available일 때만** 보인다(허용). 추가 항목:
  `Evidence(evidence_id="ev_mcst_prior_attendance", value_type="verified_fact", label="문체부 보고 전년 방문객", display_value=f"{n:,.0f}명 ({measurement}, {plan_year-1}년 실적)", numeric_value=n, unit="people", source_refs=["src_mcst_festivals"], limitation="주최 측이 문체부에 제출한 값이며 집계 방식이 축제마다 다릅니다. 예측값이 아닙니다.")`,
  `SourceRef(source_id="src_mcst_festivals", source_type="other_public", provider_name="문화체육관광부", dataset_name="연도별 지역축제 정보", source_url=SOURCE_URL, retrieved_at=<lookup 생성시각>)`. 테이블 파일 없으면 조용히 생략(경고 로그 1줄).
- lookup 테이블 경로 env `HEUNGMAP_MCST_LOOKUP_PATH`, 기본 `data/processed/mcst-attendance-lookup.csv`. lru_cache 로드.
### 7-c 스크립트 `backend/scripts/build_mcst_lookup.py --archives data/raw/mcst-festivals/*_festival.zip --output data/processed/mcst-attendance-lookup.csv` → 행 수, 연도 범위 출력. 실행 후 매칭률 측정: `festivals-2026-jan-aug.jsonl` 정규화 행 중 lookup 성공 비율을 로그·문서에 기록.
### 7-d 테스트 `backend/tests/test_attendance_lookup.py`: 합성 3행 표로 정확 일치/모호(2건)/광역 불일치 None. 개인정보 열이 표에 없음.

---

## Step 8. 설명 계층 정리 (T7) — `fix(model): 동일 라벨 요인 병합과 TreeSHAP 표기`

- `daily_service.predict_demand`: 기여도를 `FEATURE_LABELS` 라벨 기준으로 **합산**(month_sin+month_cos → "계절", weekday_0..6은 이미 하나만 1이라 사실상 하나) 후 |합|로 정렬 상위 5개. `factor_id`는 `daily_<label 첫 feature명>`.
- `explanation`: `"LightGBM TreeSHAP 기여도(pred_contrib) 기준 지역 계절 기준선 대비 약 {effect:+.2f}%. 인과효과는 아닙니다."`
- 테스트: 요인 라벨 중복 없음.
- 문서: MODEL_EVALUATION·MODEL_PLAN에서 "SHAP" 언급을 "LightGBM 내장 TreeSHAP(pred_contrib)"로 통일. `CLAUDE.md` Tier 2의 "SHAP 근거" 옆에 "(구현됨: TreeSHAP 기여도)" 표기.

---

## Step 9. 모델 카드 (T8) — `docs: 모델 카드 추가`

**신규** `docs/MODEL_CARD.md` (1~2쪽). 절: 모델명·버전 이력(1.0 → (1.1)) / 예측 대상(무엇이 아닌지 3줄) / 입력(쓰는 것·안 쓰는 것) / 학습 자료(기간·행·지역·출처 URL) / 분할과 채택 기준(5~6개) / 후향 성능표 / 전향 성능표(Step 2) / 지역 규모별 오류(Step 5) / 신뢰도·혼잡 규칙 / 한계 / 재학습 절차(명령 1개) / 발표 시 표현 지침("정확도" 금지, 대체 문구). 수치는 전부 evaluation.json·forward-evaluation.json에서.

---

## Step 10. 문서·PR 정리 (T9) — `docs: 모델 작업 기록과 역할표 정리`

1. `docs/TEAM_WORKFLOW.md` 역할표: "공유 데이터·예측 계약 관리자 | 홍성주 | ... (AI 수요 모델 포함)", "통합 검토자 | 박지성". `docs/00_START_HERE.md` §1 표도 동일 갱신.
2. `docs/MODEL_PLAN.md` "권장 모델 구조" 위에 `> 2026-09-18: 아래 그림은 초기 계획이며 실제 채택 구조는 "계절·성장 기준선 + LightGBM 잔차 보정(최대 40%)"입니다. [MODEL_CARD.md] 참조.` 인용문 추가. "역할 분담 후보" 절에 확정 담당 한 줄.
3. `docs/DECISION_LOG.md`: **D31** "제출 전 모델 운영화: 재학습 절차 고정, 전향 평가, 상태 endpoint, 지역별 신뢰도·혼잡, (축제 feature 실험 결과), 문체부 실제값 표시" — 각 Step 결과 한 줄씩, 채택/미채택 명시.
4. `docs/NEXT_SESSION_COMMAND.md`: "2026-09-18 종료 시점"으로 전면 갱신(현재 모델 버전, data_end, 마지막 예측 가능일, 재학습 명령, 남은 일).
5. `docs/MODEL_WORK_PLAN.md` 상단 일정표의 완료 항목에 ✅ 표시.
6. PR #29·#30: **[STOP]** 닫기 전에 사용자에게 "닫아도 되는지" 한 번 확인. 확인되면 `gh pr close 29 --comment "..."`, `gh pr close 30 --comment "NO-GO 기록은 DATA_GATE_REPORT.md에 보존. audit_tourapi_detail_features.py는 필요 시 별도 cherry-pick."` (Step 6에서 그 도구를 실제로 썼으면 cherry-pick 커밋을 이 브랜치에 포함하고 코멘트에 명시.)

---

## Step 11. 전체 검증 — commit 없음 (로그만)

```bash
PYTHONPATH=backend .venv/bin/pytest -q backend/tests
cd frontend && npm run lint && npx tsc --noEmit && npm run build && npx playwright test
cd .. && PYTHONPATH=backend .venv/bin/python backend/scripts/verify_daily_model.py
```
- Playwright는 자체적으로 backend 8100·frontend 3100을 띄운다(`playwright.config.ts`). 수동 uvicorn(8000)·dev(3000)와 포트가 다르므로 동시에 떠 있어도 되지만, E2E는 artifact 자동 선택 결과에 의존하므로 **Step 4 이후 실행**한다.
- uvicorn + `npm run dev`로 체험 로그인 → 기획 분석(10월 말 행사, 자동 선택된 최신 모델) → 공개 → 방문객 상세에서 **같은 prediction_id·model_version**과 신뢰도·(혼잡 등급)·(문체부 실제값) 표시 확인. 스크린샷 3장을 `docs/assets/submission-20260921/`(신규 폴더)에 저장(커밋 O, 각 500KB 이하, 개인정보·API 키 노출 없는지 확인).
- `GET /api/v1/system/model-status` 응답을 로그에 붙임.

## Step 12. 마무리 — `[STOP]` push·PR 전 확인

- 커밋 메시지 규칙: 위 각 Step 제목. 본문 끝 `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` (실제 구현 모델이 Opus면 Opus 표기).
- PR 제목 `feat(model): 제출 전 모델 운영화 (재학습·전향평가·상태점검·신뢰도·문체부 실제값)`, 본문에 Step별 결과 표와 미완료(`[SKIPPED]`) 목록, 끝에 `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
- 사용자 확인 후 push·PR. 병합은 사용자가.

## 제출 후 (P2, 이 세션 범위 밖)

T10 Windows 재현(`backend/scripts/reproduce_check.py` — fixture 학습 후 `fixtures/expected-metrics.json`과 4자리 비교), T11 artifact 포장(`package_model.py`), T12 LLM 고정 제약 검증(응답의 각 추천을 `PlannerRecommendationRequest`의 fixed 제약과 대조해 위반 시 제거 + limitation 추가). 명세는 WORK_PLAN 참조.
