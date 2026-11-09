# 공통 계약

`openapi.yaml`은 기획자·사용자 서비스가 공유하는 HTTP·JSON 계약 `0.1.0`의 기계 판독 원본이다. 사람이
읽는 의미와 불변식은 [`../docs/SHARED_SPEC.md`](../docs/SHARED_SPEC.md)에 있다.

## 파일

- `openapi.yaml`: OpenAPI 3.1.0 API와 schema
- `examples/event-list.json`: 목록·캘린더·지도 공통 응답
- `examples/planner-analysis-request.json`: 기획자 분석 요청
- `examples/planner-analysis-response.json`: 규칙 기반 분석 응답
- `examples/prediction-available.json`: 가상 규칙 score 예측 응답(`relative_demand_score`). 실제 서비스는 p10·p50·p90 방문자-일 범위를 반환하며 fixture는 schema 예시로만 유지한다
- `examples/problem.json`: 공통 오류 응답

fixture는 모두 가상 데이터이며 실제 행사, 예측 성능이나 운영 결과를 주장하지 않는다. API key, 원본 API
응답과 개인·서버 정보는 이 폴더에 넣지 않는다.

`backend/tests/test_openapi_contract.py`가 Pydantic model에서 생성한 OpenAPI와 이 계약의 field·type·필수 여부가
일치하는지 검사한다. frontend 타입(`frontend/lib/types.ts`)은 계약을 수기로 반영하며 생성 도구는 쓰지 않는다.
