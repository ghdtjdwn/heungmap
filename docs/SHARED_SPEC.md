# 공통 데이터·API 스펙 v0.1

## 목적과 상태

기획자 서비스와 사용자 서비스가 같은 행사, 장소, 예측값과 오류 의미를 사용하기 위한 첫 공통 계약이다.
두 담당자는 화면을 독립적으로 만들되 이 계약을 통해 연결한다.

- 계약 version: `0.1.0`
- HTTP base path: `/api/v1`
- 기계 판독 원본: [`../contracts/openapi.yaml`](../contracts/openapi.yaml)
- 현재 상태: 구현 시작용 v0.1 기준선
- 승인자: 공유 데이터·예측 계약 관리자 작성, 통합 검토자 검토

실제 TourAPI와 지역 방문자 데이터의 응답·결합 가능성은 아직 확인되지 않았다. 따라서 데이터 게이트에서
확인한 필드와 label에 따라 `0.1.x` 범위에서 보완할 수 있지만, 그전까지 양쪽 화면은 이 기준선과 같은 mock을
사용하고 서로 다른 임시 schema를 만들지 않는다.

## 선택한 방식

OpenAPI `3.1.0`과 JSON Schema 2020-12 호환 schema를 사용한다. FastAPI가 같은 OpenAPI version을 자동
생성할 수 있고, 이후 TypeScript client 생성에도 재사용할 수 있기 때문이다. OpenAPI 최신 version 자체를
따라가는 것보다 현재 backend 후보와 tooling 호환성을 우선한다.

오류 응답은 RFC 9457의 `application/problem+json` 구조에 흥할지도용 `code`, `retryable`, `trace_id`와
field 오류를 추가한다. 성공 응답과 오류 응답을 같은 `success` boolean envelope에 억지로 넣지 않는다.

검토한 공식 기준은 다음과 같다.

- [OpenAPI Specification](https://spec.openapis.org/oas/)
- [JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12)
- [RFC 9457 Problem Details for HTTP APIs](https://www.rfc-editor.org/rfc/rfc9457.html)
- [FastAPI의 OpenAPI client 생성 안내](https://fastapi.tiangolo.com/advanced/generate-clients/)

## 시스템 경계

```text
기획자 화면 ─┐
             ├─▶ 흥할지도 `/api/v1` ─▶ TourAPI adapter
사용자 화면 ─┘                ├──────▶ 관광 데이터랩 adapter
                              ├──────▶ 규칙·예측 model
                              └──────▶ 선택적 LLM
```

- frontend는 한국관광공사나 LLM API를 직접 호출하지 않는다.
- 외부 API key는 backend 환경 변수에만 둔다.
- 외부 응답은 adapter에서 공통 schema로 바꾸고 raw field를 화면 계약에 노출하지 않는다.
- 같은 `event_id`와 `prediction_id`를 두 서비스가 사용한다.
- LLM은 공통 `Prediction` 값을 읽기만 하며 수치를 새로 만들거나 변경하지 않는다.

## 공통 표기 규칙

| 항목 | 규칙 |
| --- | --- |
| JSON field | `snake_case` |
| 날짜 | `YYYY-MM-DD` |
| 시각 | timezone offset이 포함된 RFC 3339. 한국 시각은 `+09:00` |
| 행사 운영시간 | 출처에 시간이 없으면 만들지 않고 field를 생략 |
| 금액 | 정수 원화와 `_krw` suffix. 알 수 없으면 생략 |
| 좌표 | WGS84 decimal latitude·longitude |
| 거리 | 정수 meter와 `_m` suffix |
| 비율 | percent이면 `_pct`, 0~1 비율이면 `_ratio` |
| 알 수 없는 값 | `0`, 빈 문자열이나 임의 기본값 대신 optional field 생략 |
| enum | 소문자 `snake_case`, 화면에서만 한국어로 변환 |
| list | 값이 하나도 없으면 빈 배열. `null` list를 사용하지 않음 |

### ID

- 내부 ID는 source의 이름·날짜가 바뀌어도 유지되는 opaque string이다.
- TourAPI 행사는 `evt_tourapi_{contentid}` 형태로 생성하고 원본 `contentid`는 `source_record_id`에도 보존한다.
- 기획자 가상 행사는 `evt_planner_{uuid}` 형태를 사용한다.
- `event_id`를 화면 문구로 해석하거나 DB 정수 ID로 가정하지 않는다.
- 동일한 원본 행사를 다시 수집해도 같은 `event_id`가 만들어져야 한다.

## 데이터 출처 계약

모든 공개 행사에는 최소 한 개의 `SourceRef`가 필요하다.

| field | 의미 |
| --- | --- |
| `source_id` | 응답 안에서 evidence가 참조할 안정적인 ID |
| `source_type` | `tourapi`, `kto_datalab`, `planner_input`, `heungmap_derived`, `heungmap_model`, `weather`, `other_public` |
| `provider_name` | 화면에 표시할 제공기관 이름 |
| `dataset_name` | API·데이터셋 이름 |
| `source_record_id` | `contentid` 같은 원본 식별자. 있을 때만 제공 |
| `source_url` | 사용자가 확인할 수 있는 공식 페이지. 있을 때만 제공하며 API key가 든 호출 URL은 금지 |
| `retrieved_at` | 흥할지도가 가져온 시각 |
| `data_as_of` | 데이터가 의미하는 기준시각. 제공될 때만 사용 |

TourAPI 행사는 `provider_name`에 `한국관광공사`, `source_type`에 `tourapi`를 사용한다. 예측값에는 model
출처뿐 아니라 실제 feature에 사용한 TourAPI·관광 데이터랩 source도 연결한다.

## Event

`EventSummary`는 목록·캘린더·marker가 함께 쓰는 최소 행사 표현이다. 상세 화면도 이 field의 의미를
바꾸지 않고 `EventDetail`에서 설명·홈페이지·이미지 등을 추가한다.

필수 핵심 field는 다음과 같다.

```text
event_id
origin
visibility
title
event_type
event_status
start_date
end_date
region
sources
data_quality
updated_at
```

- `origin`: `tourapi`, `planner`
- `visibility`: `public`, `draft`; 사용자 서비스는 `public`만 표시
- `event_type`: 축제 MVP는 `festival`, `local_event`를 우선 사용하고 나머지는 확장 enum으로만 유지
- `event_status`: `scheduled`, `ongoing`, `ended`, `cancelled`, `unknown`
- 날짜 filter는 `event.start_date <= filter.end_date`이며 동시에
  `event.end_date >= filter.start_date`인 겹치는 행사를 포함
- `venue`, `coordinates`, `thumbnail`, `prediction_summary`는 실제 값이 있을 때만 제공
- 원본에 없는 운영시간, 가격, 수용인원과 편의시설을 추정해 Event fact에 넣지 않음

`data_quality`는 `completeness`와 `warnings`를 포함한다. 좌표 없는 행사는 목록·캘린더에는 남길 수 있지만
지도에는 marker를 만들지 않고 warning을 표시한다.

## Venue와 NearbyPlace

`Venue`는 행사 개최 장소이고 `NearbyPlace`는 주변 주차·숙박·음식·관광 자원이다. 같은 장소처럼 보여도
역할과 출처가 다르므로 별도 schema를 사용한다.

- 장소 이름만 확인된 경우 `Venue.name`만 제공할 수 있다.
- 공식 수용인원만 `capacity`에 넣는다. 기획자의 목표 인원은 행사 draft의 `target_attendance`다.
- `NearbyPlace.place_type`은 `parking`, `lodging`, `restaurant`, `cafe`, `tourist_attraction`,
  `cultural_facility`, `shopping`, `restroom`, `transit`, `other` 중 하나다.
- `distance_m`는 좌표로 실제 계산했을 때만 제공하고 계산 방식·기준점은 evidence로 추적한다.
- 주변 장소마다 최소 한 개의 source가 필요하다.

## Prediction

예측 endpoint는 정상적인 데이터 부족을 HTTP 오류로 처리하지 않는다. HTTP 요청 자체가 성공했다면
`PredictionResult.status`를 `available` 또는 `unavailable`로 돌려 행사 정보 흐름을 유지한다.

### available

```text
status = available
prediction_id
event_id
prediction_type
as_of
target_start_date
target_end_date
target_region                 # regional_visit_demand일 때 필수
primary_metric
components                    # prediction_type별 필요 근거
confidence
data_sufficiency
method
model_version
factors
sources
evidence
limitations
out_of_distribution
fallback_used
is_mock
created_at
```

`prediction_type`과 허용 표현은 다음과 같다.

| value | 뜻 | 화면 표현 |
| --- | --- | --- |
| `official_attendance` | 일관된 공식 관람객 label로 학습 | 예상 관람객 범위 |
| `ticket_demand` | 검표·예매·판매 label로 학습 | 예상 입장·판매 수요 |
| `regional_visit_demand` | 지역·기간 방문수요 | 지역 방문수요 범위 |
| `relative_demand_score` | 설명 가능한 합성 score | 흥행 가능성 또는 혼잡 상대지수 |

데이터 게이트가 통과하기 전에는 `official_attendance`를 반환하지 않는다. 지역 방문자 값을 특정 축제의
관람객 수나 티켓 수요로 바꿔 부르지 않는다.

`primary_metric`은 범위형 `p10·p50·p90` 또는 0~100 score 중 하나다. 다음 불변식을 backend test에서
검증한다.

- `p10 <= p50 <= p90`
- 사람 수·금액·score는 음수가 아님
- score는 0~100
- `regional_visit_demand`는 `people` 또는 `percent_change` 단위를 사용하고 화면에 지역 범위임을 표시
- `regional_visit_demand`에는 `target_region`과 지역 평상시 기준을 설명하는 `regional_baseline` component가 필요
- `relative_demand_score`는 `index_0_100` 단위 사용
- `ticket_demand_level`은 예매·판매 또는 방어 가능한 관람 수요 근거가 있을 때만 값으로 제공하고 아니면
  `unknown` 또는 field 생략
- `confidence`는 `low`, `medium`, `high`이며 성공 확률로 표현하지 않음
- `fallback_used=true`이면 규칙 기반 결과임을 화면에 표시
- `out_of_distribution=true`이면 추천을 확정 표현으로 만들지 않음

### unavailable

다음처럼 예측을 못 한 이유를 안정적인 code와 사용자 문구로 제공한다.

```text
status = unavailable
event_id
reason_code
message
as_of
sources
limitations
retryable
is_mock
```

`reason_code` 초기값은 `insufficient_data`, `unsupported_event_type`, `missing_required_input`,
`model_unavailable`, `upstream_unavailable`이다.

available·unavailable 결과 모두 `is_mock`을 포함한다. 개발 fixture는 `true`, 실제 adapter·model 결과는
`false`이며 두 값을 같은 demo 결과에 섞지 않는다.

## SearchFilter

목록·캘린더·지도는 다음 filter 의미를 공유한다.

| field | 규칙 |
| --- | --- |
| `query` | 행사명·지역 표시명 검색 |
| `start_date`, `end_date` | 행사 기간과 겹치는 결과. 둘 다 없으면 backend 기본 기간 사용 |
| `area_code`, `sigungu_code` | 정규화된 지역 code |
| `event_types` | OR 조건 |
| `sort` | `relevance`, `start_date`, `distance`, `demand` |
| `latitude`, `longitude` | `distance` 정렬 기준점. 둘을 함께 제공 |
| `south`, `west`, `north`, `east` | 지도 bounds. 네 값을 모두 제공 |
| `page`, `page_size` | 1부터 시작. `page_size` 기본 20, 최대 100 |

- 사용자 화면의 `view`, `selected_event_id`는 URL에는 보존하지만 backend search 조건은 아니다.
- `distance` 정렬에 좌표가 없으면 validation error를 반환한다.
- `demand` 정렬은 비교 가능한 prediction이 있는 행사 안에서만 사용하고 없는 행사의 배치 규칙을 고정한다.
- 같은 요청은 같은 정렬 기준과 tie-breaker `event_id`를 사용해 안정적인 순서를 만든다.

## PlannerAnalysisRequest

기획자는 일정이나 지역을 아직 정하지 못해도 분석 요청을 저장할 수 있다. `schedule_selection_mode`과
`region_selection_mode`은 각각 `fixed`, `candidates`, `recommend`, `unknown` 중 하나다.

- `fixed`이면 해당 날짜 또는 지역 field가 필요하다.
- `candidates`이면 둘 이상의 후보를 비교 대상으로 보낼 수 있다.
- `recommend`나 `unknown`이면 규칙 추천과 추가 질문은 반환하지만 필요한 정보가 없는 prediction은
  `unavailable`이다.
- `other` enum을 선택한 경우 대응하는 `_other` text를 함께 검증한다.
- 요청의 `client_request_id`는 같은 분석 버튼의 중복 전송을 식별한다. 같은 ID와 다른 body가 오면
  validation error로 처리한다.

## HTTP API v1

| method·path | 역할 | 주요 응답 |
| --- | --- | --- |
| `GET /health` | demo와 운영 상태 확인 | 외부 의존성과 분리한 process 상태 |
| `GET /events` | 목록·캘린더·지도 공통 검색 | `EventListResponse` |
| `GET /events/{event_id}` | 행사 상세 | `EventDetail` |
| `GET /events/{event_id}/nearby` | 주변 시설·관광지 | `NearbyPlaceListResponse` |
| `GET /events/{event_id}/prediction` | 같은 행사 예측 조회 | `PredictionResult` |
| `GET /venues/search` | TourAPI 장소 후보 검색 | `VenueSearchResponse` |
| `GET /addresses/search` | 주소·좌표 검색 | `AddressSearchResponse` |
| `POST /planner/analyses` | 기획자 입력 snapshot 분석 | `PlannerAnalysisResponse` |
| `POST /planner/recommendations` | Planning Context 기반 실제 LLM 추천 | `PlannerRecommendationResponse` |

현재는 로그인, draft 영구 저장·공개, 즐겨찾기, 알림과 실제 예매를 정의하지 않는다. 필요성이 확정되기
전에 인증과 DB를 공통 의존성으로 만들지 않기 위해서다.

`POST /planner/analyses`는 Tier 0에서 동기식 규칙 분석으로 시작한다. 응답에는 정규화한 요청 snapshot,
`PredictionResult`, 주변 장소의 available·unavailable 상태, 사용한 evidence와 규칙 추천이 포함된다.
장소 좌표가 없으면 주변 장소를 빈 검색 결과로 가장하지 않고 `missing_coordinates`로 설명한다.
`POST /planner/recommendations`는 같은 `analysis_id`, Planning Context와 규칙 추천을 읽는 별도 단계다.
실제 LLM의 strict JSON output과 evidence reference를 server에서 검증하며 수요 수치는 변경하지 않는다.
실패 시 frontend가 규칙 fallback을 저장해 분석 결과를 유지한다.

`GET /venues/search`는 TourAPI `searchKeyword2` 결과를 공용 `Venue`로 매핑하지만 공식 수용인원을
추정하지 않는다. `GET /addresses/search`는 Kakao Local 주소 검색 결과의 도로명·지번 주소와 좌표를
반환한다. 두 endpoint가 실패해도 기획자는 수동 입력하거나 장소를 비우고 추천 조건을 받을 수 있다.

## 성공 응답

- 단일 resource는 불필요한 공통 envelope 없이 schema 자체를 반환한다.
- list는 `items`, `page`, `page_size`, 선택적인 `total_count`, `applied_filters`와 `meta`를 반환한다.
- `meta`에는 최소 `contract_version`, `generated_at`과 `request_id`가 있다.
- 응답 field 추가는 허용하되 기존 field의 의미·type·enum을 조용히 바꾸지 않는다.

## 오류 계약

Content-Type은 `application/problem+json`이다.

```json
{
  "type": "/problems/validation-error",
  "title": "입력값을 확인해 주세요.",
  "status": 422,
  "detail": "요청한 날짜 범위를 처리할 수 없습니다.",
  "instance": "/api/v1/events?start_date=...",
  "code": "VALIDATION_ERROR",
  "retryable": false,
  "trace_id": "opaque-trace-id",
  "field_errors": [
    {"field": "end_date", "message": "start_date 이후여야 합니다."}
  ]
}
```

초기 공통 error code는 다음과 같다.

| HTTP | code | 사용 시점 |
| ---: | --- | --- |
| 400 | `INVALID_QUERY` | query 조합이 잘못됐지만 field validation보다 일반적인 경우 |
| 404 | `EVENT_NOT_FOUND` | 내부 `event_id`를 찾을 수 없음 |
| 422 | `VALIDATION_ERROR` | request field 누락·범위·조건 오류 |
| 429 | `RATE_LIMITED` | 흥할지도 자체 제한. `Retry-After` 제공 |
| 502 | `UPSTREAM_BAD_RESPONSE` | 외부 API가 해석할 수 없는 응답 반환 |
| 503 | `UPSTREAM_UNAVAILABLE` | TourAPI·관광 데이터랩 또는 model 일시 불가 |
| 504 | `UPSTREAM_TIMEOUT` | 외부 API나 이후 LLM timeout |

외부 API 원문, stack trace, key, 내부 host와 개인정보는 `detail`이나 log correlation field에 넣지 않는다.
예측만 불가한 경우에는 행사 endpoint 전체를 503으로 만들지 않고 `PredictionResult.unavailable`을 사용한다.

## mock과 실제 데이터 규칙

- mock fixture도 이 계약을 통과해야 하며 `is_mock` 같은 명시적인 표식과 가상 ID를 사용한다.
- demo에서 mock과 실데이터를 한 화면에 섞지 않는다.
- 실제 adapter가 들어오면 같은 contract를 유지하고 frontend의 mock import만 API client로 교체한다.
- 원본 API field가 사라지거나 type이 달라지면 조용히 기본값을 넣지 않고 data quality warning 또는 upstream
  error로 기록한다.
- fixture 예시는 [`../contracts/examples`](../contracts/examples)에 있다.

## version과 변경 절차

- URL의 `/v1`은 외부 HTTP contract의 major version이다.
- 문서의 `0.1.0`은 구현 전 contract revision이다.
- optional field 추가·설명 보완은 minor, 의미·type·필수 여부 변경은 breaking change로 간주한다.
- 계약 변경 PR에는 기획자 화면, 사용자 화면, model·data adapter 영향을 각각 적는다.
- 계약 관리자가 작성하고 통합 검토자가 승인한 뒤 병합한다.
- backend가 생기면 Pydantic model과 route에서 생성한 `openapi.json`이 승인 계약과 같은지 자동 검사한다.
- frontend는 손으로 response type을 중복 작성하지 않고 OpenAPI에서 TypeScript type/client를 생성한다.

## 역할별 바로 할 일

### 공통 계약 관리자

1. 실제 `searchFestival2` 응답을 보고 `Event` mapping 표를 작성한다.
2. fixture를 실제와 같은 shape로 갱신하되 원본 응답·key는 commit하지 않는다.
3. data gate 결과에 따라 활성화 가능한 `prediction_type`을 기록한다.
4. FastAPI scaffolding 시 Pydantic schema와 OpenAPI 비교 검증을 추가한다.

### 기획자 서비스 담당

1. `PlannerAnalysisRequest` fixture로 form field 이름과 단위를 고정한다.
2. `PlannerAnalysisResponse`의 예측·주변 장소 available·unavailable 상태를 화면에 연결한다.
3. LLM 없이 `rule_recommendations`를 표시하는 최소 흐름을 만든다.

### 사용자 서비스 담당

1. `EventListResponse` 하나로 목록·캘린더·marker를 구성한다.
2. 좌표·image·prediction이 없는 행사의 UI 상태를 만든다.
3. URL filter를 `GET /events` query와 일관되게 mapping한다.

## v0.1 완료 조건

- OpenAPI 문서와 JSON fixture가 문법 검증을 통과한다.
- 두 담당자가 같은 fixture로 각자의 wireflow를 설명할 수 있다.
- Event의 날짜·지역·좌표·출처 의미가 한 가지로 고정된다.
- Prediction의 종류·단위·범위·신뢰도와 unavailable 상태가 구분된다.
- 지역 방문수요가 특정 축제 관람객이나 티켓 수요로 표시되지 않는다.
- 오류·외부 API 실패 시 두 화면의 사용자 문구와 재시도 여부가 일치한다.
