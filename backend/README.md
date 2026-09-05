# 기획자 backend

FastAPI가 공통 계약 `0.1.0`의 health, 기획자 분석과 LLM 추천 endpoint를 제공한다. 분석은 입력 근거,
실제 TourAPI 조회 가능 상태, 규칙 추천과 명시적으로 표시한 mock 상대 수요 점수를 반환한다.

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements-dev.txt
PYTHONPATH=backend .venv/bin/uvicorn app.main:app --reload --port 8000
```

`TOURAPI_SERVICE_KEY`가 있으면 `searchFestival2`, `searchKeyword2`와 `locationBasedList2`를 호출한다.
`KAKAO_REST_API_KEY`가 있으면 주소 검색으로 표준 주소와 좌표를 자동 입력한다. 키나 좌표가 없거나 외부
API가 실패하면 해당 검색·근거만 `unavailable`로 반환하며 수동 입력과 규칙 결과는 유지한다.

기본 `LLM_PROVIDER=ollama`는 로컬 `qwen3.5:9b`의 structured output으로 실제 기획 문장을 생성한다.
별도 API key와 사용료는 없으며 Ollama를 실행하고 model을 내려받으면 된다. 같은 내부 계약으로 OpenAI
Responses API도 선택할 수 있고 이때만 `LLM_API_KEY`가 필요하다. 응답 schema·대안 개수·`evidence_ref`와
입력에 없는 숫자를 backend에서 검증한다. timeout, upstream 오류 또는 계약 위반 시 frontend가 로컬 규칙
보고서를 저장하므로 분석 결과는 유실되지 않는다.

장소 검색 결과에는 TourAPI가 제공한 이름·주소·좌표만 넣는다. 공식 수용인원과 대관 가능 여부는 API가
보장하지 않으므로 자동 추정하지 않고 기획자가 장소 운영자에게 확인해 입력한다.
