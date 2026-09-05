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
