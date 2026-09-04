# 공통 계약

`openapi.yaml`은 기획자·사용자 서비스가 공유하는 HTTP·JSON 계약 `0.1.0`의 기계 판독 원본이다. 사람이
읽는 의미와 불변식은 [`../docs/SHARED_SPEC.md`](../docs/SHARED_SPEC.md)에 있다.

## 파일

- `openapi.yaml`: OpenAPI 3.1.0 API와 schema
- `examples/event-list.json`: 목록·캘린더·지도 공통 응답
- `examples/planner-analysis-request.json`: 기획자 분석 요청
- `examples/planner-analysis-response.json`: 규칙 기반 분석 응답
- `examples/planner-analysis-request-large-festival.json`: 대형 지역축제 날짜 후보 요청
- `examples/planner-analysis-response-large-festival.json`: 대형 지역축제 데이터 부족 응답
- `examples/prediction-available.json`: 가상 규칙 score 예측 응답
- `examples/problem.json`: 공통 오류 응답

fixture는 모두 가상 데이터이며 실제 행사, 예측 성능이나 운영 결과를 주장하지 않는다. API key, 원본 API
응답과 개인·서버 정보는 이 폴더에 넣지 않는다.

backend가 생기기 전에는 이 파일을 승인 계약으로 사용한다. FastAPI 구현 후에는 Pydantic model에서 생성한
OpenAPI와 승인 계약의 field·type·필수 여부가 일치하는지 자동 검사하고, frontend type과 client는 OpenAPI에서
생성한다.
