# 데이터 게이트·모델 평가 보고서

실행일은 2026-09-06입니다. 원본 파일, 인증키, 학습표와 평가 artifact는 Git에서 제외하고 실제 집계와
재현 절차만 기록합니다.

## 판정

- **데이터 게이트: PASS** — 축제·지역 방문자 결합 기준을 충족했습니다.
- **LightGBM 제품 채택: NO-GO** — 시간 분할 개선 폭과 미관측 지역 일반화가 채택 기준을 충족하지
  못했습니다.
- 제품은 `MODEL MOCK` 규칙 상대지수를 유지합니다. SHAP은 채택된 모델에만 적용한다는 원칙에 따라
  계산하지 않았습니다.

| 검사 항목 | 실제 결과 |
| --- | ---: |
| 2025–2026 `searchFestival2` 원본·중복 제거 유효 행 | 688 / 673 |
| 지역 방문자 원본 행 | 464,092 |
| 방문자 구분 합산 후 일별 기초지자체 행 | 154,706 |
| 결합 행 | 514 |
| 결합률 | 76.37% |
| 결합 학습표 기초지자체 수 | 176 |
| 행사 원본 중복률 | 2.18% |
| 축제 좌표 결측률 | 0.15% |
| gate 기준 | 결합 50행 이상이면서 70% 이상 |

TourAPI의 `lDongRegnCd` 2자리와 `lDongSignguCd` 3자리를 방문자 API의 `signguCode` 5자리로 정규화했습니다.
행사 기간 모든 날짜의 값과 행사 전 28일 중 최소 14일의 값이 있을 때만 결합했습니다. 원본 방문자의
현지인·외지인·외국인 구분을 같은 날짜·기초지자체 안에서 합산했으며 광역·기초 집계를 섞지 않았습니다.

- [국문 관광정보 서비스 `searchFestival2`](https://www.data.go.kr/tcs/dss/selectApiDataDetailView.do?publicDataPk=15101578)
- [한국관광공사 지역별 방문자수](https://www.data.go.kr/data/15101972/openapi.do)

지역 방문자 값은 이동통신 기반 지역 방문자-일 집계입니다. 동일인이 여러 날 방문하면 날짜별로 포함될
수 있으며 특정 축제 입장객이나 실제 혼잡 관측이 아닙니다.

## label 결정안

| 후보 | 단위 | 장점 | 한계·누수 위험 | 화면 표현 |
| --- | --- | --- | --- | --- |
| 행사 기간 일평균 | 지역 방문자-일/일 | 정의가 단순함 | 지역 규모와 동시 행사를 포함 | 행사 기간 지역 방문수요 |
| 직전 28일 중앙값 대비 증가분 | 지역 방문자-일/일 | 변화량을 직접 표현 | 큰 지역에 좌우됨 | 평상시 대비 지역 방문수요 증가분 |
| **직전 28일 중앙값 대비 증가율** | 비율 | 지역 규모를 정규화 | 낮은 기준선 변동, 동시 행사·계절 영향 | 평상시 대비 지역 방문수요 증감률 |
| 지역 방문수요 상대지수 | 기준선 100 | 설명·등급화가 쉬움 | 실제 혼잡이나 관람객 수가 아님 | 지역 방문수요 상대지수 |

게이트용 추천 label은 `regional_daily_visitor_uplift_rate`입니다. 행사 기간 일평균 방문자 수에서 직전
28일 중앙값을 빼고 그 중앙값으로 나눈 비율입니다. 학습의 정답에만 행사 기간 방문자를 사용하고 입력
feature에는 포함하지 않습니다. 최종 이름·단위·UI 문구는 공통 계약이므로 **공동 검토 대기**입니다.

## 실제 baseline·LightGBM 평가

평가 feature는 기획 시점에 알 수 있는 월, 요일, 행사 기간, 광역 코드, 위도, 경도만 사용했습니다.
행사 기간 방문자·label 파생값·사후 검색·SNS·소비를 제외했습니다. 행사 직전 28일 방문자 중앙값도 먼
미래의 기획 시점에는 알 수 없으므로 모델 입력에서 제외했습니다.

| 평가 | 지역 중앙값 baseline | LightGBM | 결론 |
| --- | ---: | ---: | --- |
| 시간 분할 MAE, 410학습/104평가 | 0.077481 | 0.090058 | LightGBM 16.23% 악화 |
| 시간 분할 RMSE | 0.107295 | 0.112791 | LightGBM 악화 |
| 미관측 지역 5-fold 평균 MAE | 0.103730 | 0.100590 | LightGBM 소폭 개선 |

표본은 2025–2026년 514건입니다. 다년·평가 표본 기준과 미관측 지역 MAE 기준은 통과했지만 시간 분할
MAE와 RMSE가 baseline보다 나빠 채택 기준을 통과하지 못했습니다. 따라서 model artifact를 제품에 연결하지 않고
`model_adopted=false`, `shap_status=not_computed_model_not_adopted`로 기록했습니다.

## feature 판정

| 상태 | feature |
| --- | --- |
| 사용 가능 | 달력·요일·계절, 행정 코드, TourAPI 행사 기본 정보, 기획자 입력 장소 유형·목표 규모·예산 구간 |
| 추후 가능 | 예측 시점 이전의 지역 방문자 lag, 검증된 공식 수용인원, 당시 실제 제공된 기상 예보, 과거 기후 통계 |
| 누수 위험 | 행사 기간 방문자·소비·검색량, 미래 기간 이동평균·지역 순위, 행사 후 SNS 반응 |
| 제외 | 확인되지 않은 실제 관람객 수, 사후 매출·성과, 출처·이용조건 미확인 민간 인기 지표 |

날씨 API 키가 없고 먼 미래 행사에는 실제 단기예보가 존재하지 않으므로 현재 feature에서 제외합니다.
예측 시점별 당시 예보 snapshot을 보관할 수 있을 때만 추가합니다.

## 재현

수집기는 pagination, timeout, bounded retry, 요청 간격, 완료 page 이후 재개와 원본 조회시각을 지원합니다.

```bash
PYTHONPATH=backend .venv/bin/python -m app.data_gate.cli collect festivals \
  --start 20250101 --end 20251231 --rows 1000 --max-pages 5 \
  --output data/raw/festivals-2025.jsonl

PYTHONPATH=backend .venv/bin/python -m app.data_gate.cli collect festivals \
  --start 20260101 --end 20260831 --rows 1000 --max-pages 5 \
  --output data/raw/festivals-2026-jan-aug.jsonl

PYTHONPATH=backend .venv/bin/python -m app.data_gate.cli collect visitors \
  --start 20250101 --end 20251231 --rows 10000 --max-pages 40 \
  --output data/raw/visitors-2025-full.jsonl

PYTHONPATH=backend .venv/bin/python -m app.data_gate.cli collect visitors \
  --start 20260101 --end 20260831 --rows 10000 --max-pages 25 \
  --output data/raw/visitors-2026-jan-aug.jsonl

PYTHONPATH=backend .venv/bin/python -m app.data_gate.cli build \
  --festivals data/raw/festivals-2025.jsonl data/raw/festivals-2026-jan-aug.jsonl \
  --visitors-jsonl data/raw/visitors-2025-full.jsonl data/raw/visitors-2026-jan-aug.jsonl

.venv/bin/pip install -r backend/requirements-model.txt
PYTHONPATH=backend .venv/bin/python backend/scripts/evaluate_demand_model.py
```

## 공통 계약 검토 자료

- [x] 원본 출처, 조회시각, 지역·기간, 파생식 보존
- [x] 지역 방문자와 특정 축제 관람객 표현 분리
- [x] 모델 채택 기준과 실패 결과 기록
- [x] 공통 `Event`, `Prediction`, `SourceRef`, `Problem` 재사용
- [ ] label 이름·단위·UI 문구 두 팀원 승인 — **공동 검토 대기**
- [ ] 기획자·방문객 화면의 동일 prediction 계약 확인 — **공동 검토 대기**

## 2026-09-11 v2 재평가

### 최신 API snapshot

동일한 수집 명령을 다시 실행하자 외부 API 갱신으로 원본 행 수가 달라졌습니다. 원본과 결과 artifact는
Git에서 제외하고 아래 집계와 실행 절차만 기록합니다.

| 항목 | 2026-09-06 | 2026-09-11 |
| --- | ---: | ---: |
| `searchFestival2` 원본 행 | 688 | 654 |
| 중복 제거 유효 축제 | 673 | 639 |
| 지역 방문자 원본 행 | 464,092 | 468,934 |
| 일별 기초지자체 행 | 154,706 | 156,320 |
| 결합 학습표 | 514 | 493 |
| 결합률 | 76.37% | 77.15% |

최신 snapshot도 데이터 게이트 기준인 50건·70%를 통과합니다. 행 수 차이는 외부 데이터가 갱신된
결과이며 이전 수치를 덮어쓰지 않습니다.

### 다년 확대 시도

지역 방문자 API에서 2022년 12월~2024년 자료 599,940행을 추가 수집했습니다. 그러나 현재
`searchFestival2`가 2023년 축제 2건, 2024년 축제 4건만 반환해 중복 제거 후 실제 학습표는 493건에서
495건으로 2건만 늘었습니다. 방문자 자료만으로는 행사 feature와 label 행을 만들 수 없으므로 이 표를
제품 모델 개선 근거로 사용하지 않습니다.

과거 축제 snapshot을 공식 출처와 조회시각을 보존한 형태로 확보하기 전에는 다년 표본 확대를 완료한
것으로 주장하지 않습니다.

### 평가 방법 개선

`backend/scripts/evaluate_demand_model_v2.py`를 추가했습니다.

1. 마지막 20% 시간 구간은 최종 평가 전까지 후보 선택에서 제외합니다.
2. 앞선 80%를 5개 날짜 block으로 나눠 expanding rolling origin 3개 fold를 만듭니다.
3. v1 L2 LightGBM, MAE용 L1 LightGBM과 기초지자체 범주를 포함한 L1 후보를 비교합니다.
4. L1 후보에는 행사 일정에서 계산 가능한 연중 순환 날짜, 주말 일수·비율과 시작·종료 주말 여부만
   추가합니다.
5. 별도로 표본이 적은 지역 평균을 전체 평균 쪽으로 수축한 설명 가능한 baseline을 함께 보고합니다.
6. rolling 평균 MAE로 선택한 한 후보만 마지막 시간 구간과 미관측 지역 5-fold에서 평가합니다.

행사 기간 방문자, label 파생값, 사후 검색·소비와 먼 미래 기획 시점에 알 수 없는 직전 28일 실제
방문자는 계속 제외했습니다. 동시 행사 수는 최신 TourAPI snapshot으로 과거 공개 시점의 가용성을
증명할 수 없어 이번 feature에서 제외했습니다.

### 실제 결과

| 평가 | 지역 중앙값 baseline | 정규화 지역 평균 baseline | 선택 L1 달력 LightGBM |
| --- | ---: | ---: | ---: |
| 훈련 구간 rolling 평균 MAE | 0.123001 | fold별 참고값 기록 | 0.115853 |
| rolling MAE 개선률 | 기준 | — | 5.81% |
| 최종 시간 분할 MAE | 0.077315 | **0.071073** | 0.085256 |
| 최종 시간 분할 RMSE | 0.104856 | **0.093801** | 0.115045 |
| 최종 MAE 개선률 | 기준 | 8.07% | **-10.27%** |
| 미관측 지역 5-fold 평균 MAE | 0.105840 | 해당 없음 | 0.100143 |
| 미관측 지역 MAE 개선률 | 기준 | — | 5.38% |

rolling 검증이 선택한 후보는 `lightgbm_l1_calendar`였지만 10% 개선 기준을 넘지 못했고 마지막 시간
구간에서 악화됐습니다. 정규화 지역 평균은 기존 baseline보다 나았지만 개선률이 10%에 못 미치는
설명 가능한 baseline 후보일 뿐, 학습 모델 채택 근거가 아닙니다.

### 최종 시간 구간 오차 분석

최종 103건을 실제 uplift 구간별로 나누면 전체 평균 metric만으로 보이지 않던 오류 방향이 드러납니다.
아래 값도 실제 축제 관람객 오차가 아니라 지역 방문수요 uplift rate의 오차입니다.

| 실제 uplift 구간 | 행 수 | 지역 중앙값 MAE | L1 달력 모델 MAE | 모델 개선률 | 모델 평균 오차 |
| --- | ---: | ---: | ---: | ---: | ---: |
| -5% 미만 감소 | 7 | 0.091478 | 0.140809 | -53.93% | +0.140809 |
| -5%~+5% 보합 | 30 | 0.038206 | 0.071625 | -87.47% | +0.071341 |
| +5% 초과 증가 | 66 | 0.093590 | 0.085561 | +8.58% | -0.055139 |

모델의 전체 평균 오차는 -0.004983으로 작지만 이는 구간별 반대 방향 오류가 상쇄된 결과입니다. 감소·보합
행사를 과대평가하고 증가 폭이 큰 행사를 과소평가하므로, 일정과 좌표만으로는 행사 자체의 수요 강도를
구분하지 못하고 중간 범위로 수축하는 패턴입니다.

월별로도 6월은 baseline보다 5.33%, 7월은 23.10% 악화됐습니다. 8월은 36.82% 개선됐지만 9건뿐이라
일반화 근거로 사용하지 않습니다. 광역 단위 결과도 일부 표본이 1~2건에 불과해 지역별 우열을 주장하지
않고 JSON에 행 수와 함께 진단값만 남깁니다.

다음 feature 검증 우선순위는 행사 전에 확보 가능한 TourAPI 행사 유형·상세 소개·주최 정보와 공휴일·연휴
구성입니다. 먼저 상세 endpoint의 실제 제공률과 결측률을 확인하고, 유효한 항목만 별도 후보로 등록합니다.
행사 기간 방문자나 label 파생값으로 위 오류를 직접 맞추는 방식은 계속 금지합니다.

판정은 계속 **LightGBM 제품 채택 NO-GO**입니다. 제품은 mock 상대지수와 규칙 fallback을 유지하고
SHAP 및 model artifact 생성을 시작하지 않습니다.

```bash
PYTHONPATH=backend .venv/bin/python backend/scripts/evaluate_demand_model_v2.py \
  --input data/processed/training-table-v1.csv \
  --output data/processed/model-evaluation-v2.json
```

평가 명령은 채택 기준 미통과 시 의도적으로 종료 코드 `2`를 반환합니다. JSON의
`model_adopted=false`, `rejection_reasons`와 fold별 metric이 실제 결과입니다.
