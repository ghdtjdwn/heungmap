# 데이터와 API

## 데이터 조립

여러 API의 응답을 공통 키인 지역과 기간으로 결합해 하나의 학습표를 만듭니다. 결과 표의 한 행은 축제
하나를 나타냅니다.

| 축제명 | 지역(시군구) | 시작월 | 기간(일) | 카테고리 | 작년방문자 | 주말수 | 평균기온 | ... | label: 방문자수 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

- features: 지역, 시기, 기간, 카테고리, 과거 방문자, 날씨, 주말 포함 여부 등
- label: 축제 기간 방문자 수 또는 평상시 대비 증가분

## 데이터 소스

| 소스 | 용도 | 비고 |
| --- | --- | --- |
| TourAPI `searchFestival2` | 축제명, 시기, 기간, 지역 코드, 카테고리, `contentid` | 축제 탐색의 기준 데이터 |
| 한국관광 데이터랩 지역별 방문자 수 | 지역·기간별 방문자 시계열 | label 후보 |
| 기상청 API | 축제 기간 날씨 | 모델 단계에서 선택적으로 추가 |
| 공연·출연진 공개 지표 | 프로그램 관심도 후보 | 출처와 이용 조건이 명확할 때만 사용 |

API key는 `.env`에 저장하고 원본 응답은 ignored `data/raw/` 경로에서 관리합니다. TourAPI 안내는
<https://api.visitkorea.or.kr>, 관광 데이터랩 안내는 <https://datalab.visitkorea.or.kr>에서 확인합니다.
전체 후보와 흥할지도 활용 판단은 [OpenAPI 카탈로그](OPENAPI_CATALOG.md)에 정리합니다.
모델의 전체 입력·출력 후보와 누수 방지 기준은 [AI 모델 계획](MODEL_PLAN.md)에 정리합니다.
정규화한 행사·출처와 오류 field는 [공통 스펙](SHARED_SPEC.md)을 사용합니다.

## 조립 과정

1. 수집: API를 호출해 원본 JSON을 `data/raw/`에 저장합니다.
2. 파싱: 응답 schema를 검증하고 pandas DataFrame으로 변환합니다.
3. 결합: 축제표와 방문자표를 지역 코드와 기간으로 결합합니다.
4. 파생: 개최 기간, 주말 수와 과거 동일 축제 방문자 등 feature를 계산합니다.
5. 정제: label 정의, 결측과 이상치 처리 규칙을 기록하고 `data/processed/train.csv`를 생성합니다.

결합 개념은 다음과 같습니다.

```python
merged = festivals.merge(visitors, on=["area_code", "yyyymm"], how="left")
merged = merged.merge(weather, on=["area_code", "yyyymm"], how="left")
```

## 데이터 검증 게이트

본격적인 모델링 전에 축제에 방문자 label을 설명 가능한 방식으로 연결할 수 있는지 확인합니다.

### 1단계 — TourAPI 축제 표본

Python 3.11 이상에서 별도 package 설치 없이 실행합니다. `.env.example`을 `.env`로 복사하고
`TOURAPI_SERVICE_KEY`에 공공데이터포털의 일반 인증키(Decoding)를 저장한 뒤 조회 기간을 지정합니다.

```bash
cp .env.example .env
python3 scripts/fetch_tourapi_festivals.py \
  --start-date 20250101 \
  --end-date 20251231 \
  --rows 100
```

스크립트는 `searchFestival2` JSON 원본을 `data/raw/tourapi/`에 저장하고, 표본 수·중복 ID·필수 필드
누락 수를 `data/processed/data_gate/`에 요약합니다. 두 경로는 Git에서 제외됩니다. API key는 요청에만
사용하며 console, 원본 파일과 요약 파일에 기록하지 않습니다. 같은 경로를 명시해 다시 실행할 때는 기본적으로
기존 파일을 덮어쓰지 않습니다.

결과의 `gate_status`가 `tourapi_sample_ready`여도 TourAPI 표본 단계만 통과한 것입니다. 지역별 방문자
데이터를 같은 지역·기간 단위로 수집하고 결합하기 전에는 축제별 label이나 관람객 수를 확정하지 않습니다.

수집 코드의 네트워크 없는 검증은 다음과 같이 실행합니다.

```bash
python3 -m unittest discover -s tests -v
```

- [ ] `TOURAPI_SERVICE_KEY`, `VISITOR_API_SERVICE_KEY` 발급
- [ ] `searchFestival2`에서 과거 축제명, 지역과 기간 수집
- [ ] 같은 지역·기간의 방문자 값 수집
- [ ] 지역 코드와 기간으로 결합하고 유효 행 수와 결합률 측정
- [ ] label 후보별 의미, 집계 단위, 누락과 잠재적 누수 기록
- [ ] 학습과 검증에 필요한 표본 수가 확보되는지 판단

축제별 label의 의미와 품질을 설명할 수 있으면 축제 수요 예측을 진행합니다. 지역 단위 집계만 가능하거나
표본이 부족하면 지역별 관광 혼잡 예측으로 범위를 전환합니다. 임의 보간으로 데이터 한계를 숨기지 않습니다.
