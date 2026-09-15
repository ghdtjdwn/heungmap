# 지역 방문수요 D-30 모델 실행·평가 — 2026-09-15

현재 서비스 기본 모델은 `regional-daily-1.0-3e0451e58b0c`입니다. 행사 시작 30일 전을 기준으로
공표 지연 30일을 추가 가정해, 목표일 60일 전까지 확인 가능한 한국관광공사 시군구 방문자 이력만으로
행사기간의 **지역 전체 방문자-일 합계**를 예측합니다. 특정 축제 관람객·고유 방문자·티켓 수요·혼잡도나
축제의 인과효과가 아닙니다.

모델·학습표·원본과 checksum manifest는 Git 제외 경로
`data/processed/daily-forecast-production-v3/`에 있습니다. 서버 배포·커밋·push는 하지 않았습니다.

## 바로 확인하기

```bash
.venv/bin/pip install -r backend/requirements-model.txt

PYTHONPATH=backend .venv/bin/python backend/scripts/train_daily_forecast.py \
  --output-dir data/processed/daily-forecast-reproduction \
  --validation-start 2026-07-01 --test-start 2026-08-01

PYTHONPATH=backend .venv/bin/pytest -q backend/tests
PYTHONPATH=backend .venv/bin/uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev
```

다른 채택 artifact를 쓰려면 `HEUNGMAP_DAILY_MODEL_DIR=/absolute/path/to/model-run`을 backend 환경에
설정합니다. manifest·평가·모델·이력 checksum 중 하나라도 다르거나 채택 조건이 하나라도 실패하면
모델을 제공하지 않습니다.

## 데이터와 예측 시점

| 항목 | 관측 결과 |
| --- | ---: |
| 방문자 구분별 원본 | 471,355행 |
| 3개 방문자 구분이 모두 있는 지역·일 | 157,110행 |
| 원본 관측 기간 | 2025-01-01~2026-08-15 |
| D-30 학습·평가표 | 37,692행·264시군구 |
| 학습 | 26,928행, ~2026-06-30 |
| 전진 검증 | 15,174행, 2026년 6월·7월 |
| 최종 시간 홀드아웃 | 3,510행, 2026-08-01~08-15 |

현지인·외지인·외국인 세 구분을 날짜·시군구별로 중복 제거한 뒤 모두 존재하는 날만 합산합니다.
결측을 0으로 채우지 않습니다. 각 목표일의 기준선은 전년도 같은 요일 주변 3개 값의 중앙값에,
목표일 60일 전까지 관측한 최근 28일 지역 연간 성장률을 곱합니다. LightGBM은 이 강한 기준선의
로그 잔차를 최대 40%만 보정합니다. 입력은 기준선, 연간 성장, 최근 추세·변동성, 60/67/74일 전 수요,
월과 요일이며 목표일 이후 값·실제 행사기간 값·날씨·예산·출연진은 사용하지 않습니다.

## 관측 성능

아래 수치는 2026년 8월 1~15일의 3,510개 지역·일 후향 시간 홀드아웃에서 실제 관측한 값입니다.
WAPE나 중앙 절대비율오차를 `정확도 96%`처럼 바꿔 말하지 않습니다.

| 방법 | WAPE | 중앙 절대비율오차 | RMSLE | ±20% 이내 |
| --- | ---: | ---: | ---: | ---: |
| 계절·성장 기준선 | 4.072% | 3.436% | 0.07039 | 97.75% |
| 채택 LightGBM 결합 | **3.809%** | **3.351%** | **0.07003** | **97.81%** |

- WAPE는 기준선보다 6.46% 상대 개선됐습니다.
- 80% split-conformal 구간의 실제 포함률은 78.21%였습니다.
- WAPE·RMSLE 기준선 우위, 중앙오차 10% 미만, ±20% 포함률 75% 이상, 구간 포함률 75% 이상 등
  사전 정의한 5개 조건을 모두 통과했습니다.
- 후보는 6월·7월 전진검증 WAPE로 골랐고 최종 설정은 L1 LightGBM
  (`num_leaves=11`, `min_child_samples=120`, `n_estimators=180`, `learning_rate=0.025`)과
  계절 기준선의 40% 잔차 보정입니다.

이는 실제로 관측한 강한 성능이지만, 개발 중 이전 7~8월 합산 평가를 확인한 뒤 보수적 보정 상한을 정한
후향 실험입니다. 따라서 완전히 손대지 않은 전향 시험이나 미래 운영 정확도로 주장하지 않습니다.
발표에서는 `최근 시간 홀드아웃 성능`으로 표현하고 운영 후 새 날짜를 고정 평가해야 합니다.

## 문체부 축제별 실제 방문객 자료 감사

문체부 공식 연도별 지역축제 ZIP 2017~2026년 10개를 직접 수집했습니다. 총 10,198개 축제 행이며,
연도별 파일의 `방문객수(前년)`를 인접 연도 동일 광역·기초지자체와 회차·연도를 제거한 정확 축제명으로만
연결했습니다. 퍼지 매칭은 쓰지 않았습니다. 예산·양수 전년도 실적 조건까지 만족한 학습쌍은 3,541개입니다.

축제별 후보 모델 `festival-attendance-1.0-5b674ca2bec5`는 2025년 실적 680건에서 RMSLE를 전년도
단순값보다 1.65% 개선했지만, 중앙 절대비율오차가 18.03%에서 20.34%로 나빠졌습니다. 따라서
`data/processed/attendance-model-release/`에 **미채택**으로 보존했고 서비스에는 연결하지 않았습니다.
2025년 라벨 중 다음 해 문체부 파일에서 계측 254건, 추정 160건, 방법 무응답 266건으로 확인돼
집계방식 혼합도 명시합니다.

```bash
PYTHONPATH=backend .venv/bin/python backend/scripts/collect_mcst_festivals.py \
  --output-dir data/raw/mcst-festivals-new

PYTHONPATH=backend .venv/bin/python backend/scripts/train_attendance_model.py \
  --archives data/raw/mcst-festivals-new/*_festival.zip \
  --output-dir data/processed/attendance-model-reproduction
```

자료 출처는 [문화체육관광부 연도별 지역축제 정보](https://www.mcst.go.kr/site/s_culture/festival/festivalList.jsp)와
[공공데이터포털 메타데이터](https://www.data.go.kr/data/15143175/fileData.do)입니다. XLSX에는 담당자 정보도
있지만 모델 파이프라인은 연락처·성명을 읽거나 가공표에 저장하지 않습니다.

## 서비스 출력과 한계

응답은 `prediction_type=regional_visit_demand`, `unit=people`로 행사기간 날짜별 시군구 방문자 수를
합산한 p10/p50/p90 범위, 계절 기준선, ML 기여요인과 출처를 제공합니다. 같은 사람이 여러 날 방문하면
중복되는 방문자-일 단위입니다. 관측 근거 없는 티켓 수요와 혼잡 등급은 `unknown`으로 유지합니다.

지원 범위는 오늘부터 30일 이내 시작하는 1~30일 행사, 완전한 전년·최근 이력이 있는 264개 시군구입니다.
현재 원본으로 마지막으로 계산 가능한 목표일은 2026-10-14입니다. 이력 누락·60일 초과 노후화·artifact
손상·미채택 상태에서는 숫자를 만들지 않고 `unavailable`을 반환합니다.

공표 지연 30일은 과거 공개 snapshot이 없어 둔 보수적 가정이며 실제 API SLA를 증명한 값은 아닙니다.
한 해 남짓한 이력이라 명절 날짜 이동, 기상이변, 대형 사건을 충분히 학습하지 못합니다. 운영 배포 전에는
두 팀원의 계약·표현 검토, Windows 재현, 새 날짜 전향 평가가 남아 있습니다.

방법·데이터 근거: [한국관광공사 지역별 방문자수](https://www.data.go.kr/data/15101972/openapi.do),
[LightGBM 공식 문서](https://lightgbm.readthedocs.io/en/stable/Parameters.html).

## 이번 로컬 검증

- backend: `124 passed`(로컬 API 키를 차단한 격리 환경, deprecation 경고 3건)
- frontend: TypeScript 검사, ESLint, Next.js production build 통과
- Playwright: desktop·mobile `24 passed`
- 실제 채택 artifact + 격리된 임시 SQLite: 체험 로그인 → 기획 분석 200 → 공개 200 → 방문객 예측 조회에서
  동일 prediction ID·모델 버전·방문자-일 범위를 확인했습니다. 실계정·운영 DB·배포는 사용하지 않았습니다.
