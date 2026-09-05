# 문제 해결 기록

## 지역별 방문자수 API가 활용 권한 오류를 반환하는 경우

- 날짜: 2026-09-06
- 상황: TourAPI `searchFestival2`에 성공한 공공데이터포털 일반 인증키로 한국관광공사 지역별 방문자수
  `locgoRegnVisitrDDList`를 smoke 호출했습니다.
- 기대 동작: 같은 기간·지역의 일별 방문자 행을 받아 축제 기간과 직전 기준선을 결합해야 합니다.
- 실제 동작과 영향: 최초 API가 활용 권한 오류를 반환해 방문자 0행, 결합 0행·0%가 됐습니다.
- 원인: 공공데이터포털의 국문 관광정보 서비스와 지역별 방문자수는 별도 활용신청 대상입니다. 한 서비스의
  키가 정상이어도 다른 서비스 권한이 자동으로 생기지 않습니다.
- 해결 방법: <https://www.data.go.kr/data/15101972/openapi.do>에서 별도 활용신청 후 승인된 일반 인증키를
  `.env`의 `VISITOR_API_SERVICE_KEY`에 설정합니다. 키를 코드·문서·로그에 넣지 않습니다.
- 재검증: 승인 키로 2025–2026 원본 464,092행, 일별 기초지자체 154,706행을 수집했고 TourAPI 축제와
  514건·76.37%를 결합해 데이터 게이트를 통과했습니다. 이후 모델 평가는 별도로 채택 기준에 실패했습니다.
- 회귀 방지: 수집기는 permission, quota, timeout, upstream, invalid response를 분리하고 완료 page부터
  재개합니다. 실제 데이터가 없을 때는 빈 label이나 평가 metric을 생성하지 않습니다.

## macOS에서 LightGBM이 `libomp.dylib`를 찾지 못하는 경우

- 날짜: 2026-09-06
- 상황: Apple Silicon macOS의 Python 가상환경에 LightGBM wheel을 설치하고 실제 평가 script를 실행했습니다.
- 실제 동작과 영향: import 단계에서 `Library not loaded: @rpath/libomp.dylib` 오류가 발생해 모델 학습을
  시작하지 못했습니다.
- 원인: LightGBM의 macOS wheel이 사용하는 OpenMP runtime이 시스템에 설치되지 않았습니다.
- 해결: `brew install libomp` 후 같은 가상환경에서 LightGBM import와 학습을 다시 실행했습니다.
- 검증: 시간 분할과 5-fold 지역 group 평가가 끝까지 실행돼 JSON 평가 report를 생성했습니다.
- 재발 방지: macOS 모델 재현 절차에 Homebrew `libomp`를 명시합니다. Windows wheel에는 같은 Homebrew
  단계가 없으므로 Windows 체크리스트에 그대로 적용하지 않습니다.

## Ollama structured output이 `failed to parse grammar`를 반환하는 경우

- 날짜: 2026-09-06
- 상황: Pydantic이 생성한 전체 `PlannerRecommendationContent` JSON Schema를 Ollama `/api/chat`의
  `format`에 전달했습니다.
- 기대 동작: `qwen3.5:9b`가 schema에 맞는 한국어 기획 보고서를 반환해야 합니다.
- 실제 동작과 영향: Ollama가 HTTP 400과 `Failed to initialize samplers: failed to parse grammar`를
  반환해 LLM 보고서만 규칙 fallback으로 전환됐습니다.
- 재현과 증거: nullable `anyOf`와 boolean `const`를 호환 형태로 바꾼 뒤에도 실패했고, 문자열
  `minLength`·`maxLength`를 제외하면 같은 nested schema가 HTTP 200으로 생성되는 것을 분리 확인했습니다.
- 원인: 현재 로컬 Ollama grammar parser가 Pydantic schema의 문자열 길이 제약을 처리하지 못했습니다.
- 대안과 해결: Ollama 생성용 schema에서 문자열 길이 annotation만 제거하고 nullable field는 non-null
  생성형으로, `const`는 단일 `enum`으로 바꿉니다. 요청한 대안 개수는 `minItems`·`maxItems`로 강제합니다.
  생성 뒤에는 원본 Pydantic model로 길이·필수값·enum·추가 필드 전체를 다시 검증하므로 application 계약은
  완화하지 않습니다.
- 검증: adapter 회귀 test와 실제 `qwen3.5:9b` 호출에서 HTTP 200, Pydantic 계약, 대안 개수, 근거 참조,
  숫자 주장과 사람 확인 표시를 모두 통과했습니다.
- 회귀 방지와 남은 위험: Ollama version을 바꿀 때 generation schema와 원본 검증을 함께 실행합니다.
  model이 계약을 어기면 자동 수정하거나 재시도하지 않고 규칙 fallback을 사용합니다.

## Next.js 개발 rewrite가 로컬 LLM 장시간 요청을 끊는 경우

- 날짜: 2026-09-06
- 상황: 브라우저와 FastAPI 사이의 일반 API rewrite로 로컬 LLM 보고서 요청도 전달했습니다.
- 기대 동작: frontend 제한 안에서 LLM 응답을 기다린 뒤 구조화 보고서를 표시해야 합니다.
- 실제 동작과 영향: FastAPI 직접 호출은 성공했지만 Next.js 개발 rewrite 경로는 약 30초 뒤 본문 없는
  HTTP 500을 반환했습니다. 입력과 분석 결과는 보존되고 규칙 fallback으로 전환됩니다.
- 원인과 증거: 같은 payload의 FastAPI 직접 호출은 약 60초 뒤 성공했고, rewrite 경로만 약 30초에
  끊겼습니다. 일반 health rewrite와 FastAPI CORS preflight는 HTTP 200이었습니다.
- 해결: 현재 localhost 범위에서 LLM 요청만 `NEXT_PUBLIC_API_BASE_URL` 또는 기본
  `http://127.0.0.1:8000`으로 직접 보내고, FastAPI는 허용된 localhost frontend origin에만 CORS를
  허용합니다. 검색·일반 분석은 기존 same-origin rewrite를 유지합니다.
- 검증: FastAPI CORS preflight의 허용 origin·method·header와 실제 구조화 LLM 응답을 확인했습니다.
- 회귀 방지와 남은 위험: 서버 배포를 시작할 때는 same-origin reverse proxy의 read timeout을 실제 추론
  시간보다 길게 설정하고 이 로컬 직접 주소를 배포 환경값으로 교체해야 합니다.

## OpenAI Responses API가 429 `credit_balance_exhausted`를 반환하는 경우

- 날짜: 2026-09-06
- 상황: project API key와 가장 저렴한 `gpt-5-nano`를 로컬 backend에 설정하고 실제 구조화 추천을
  호출했습니다.
- 기대 동작: `POST /v1/responses`가 strict JSON Schema에 맞는 기획 추천을 반환해야 합니다.
- 실제 동작과 영향: OpenAI가 HTTP 429 `insufficient_quota`, `credit_balance_exhausted`를 반환했습니다.
  모델·endpoint·인증까지는 도달했지만 계정 credit이 없어 실제 본문 생성은 시작되지 않았습니다.
- 재현: `LLM_API_KEY`를 설정한 뒤 `POST /api/v1/planner/recommendations`를 호출합니다. key와 요청 본문은
  로그에 남기지 않습니다.
- 확인한 가설: key 누락이나 model 미지원이 아니라 provider가 반환한 machine-readable error code로
  credit 부족을 확인했습니다.
- 원인: 해당 OpenAI organization/project에 사용 가능한 API credit이 없습니다.
- 대안: 현재 구현된 규칙 fallback으로 입력·mock prediction·보고서·내보내기를 계속 사용할 수 있습니다.
- 현재 기본 provider는 비용이 없는 로컬 Ollama로 전환했습니다. 이 기록은 선택적으로 OpenAI adapter를
  다시 사용할 때만 적용됩니다.
- 해결 방법: OpenAI billing 화면에서 API credit을 추가하고 project spending limit을 확인한 뒤 같은
  idempotent 요청을 새 `client_request_id`로 한 번 실행합니다.
- 검증: backend가 provider 429를 503 `LLM_UPSTREAM_UNAVAILABLE`, `retryable=true`로 변환하고 frontend가
  규칙 보고서로 전환할 수 있는 것까지 확인했습니다. 실제 `generation_mode=llm` 경로는 로컬 Ollama로
  별도 검증했습니다.
- 회귀 방지와 남은 위험: 자동 재시도는 하지 않고 요청당 한 번만 호출합니다. 계정 rate limit이나 spend
  limit에서도 429가 발생할 수 있으므로 provider error code를 비밀값 없이 구분해 기록합니다.

## Kakao Local 주소 검색이 403을 반환하는 경우

- 날짜: 2026-09-06
- 상황: 유효한 형식의 Kakao REST API 키를 backend에 설정하고 주소 검색을 호출했습니다.
- 기대 동작: `GET /v2/local/search/address.json`이 주소와 좌표를 반환해야 합니다.
- 실제 동작과 영향: Kakao가 HTTP 403 `NotAuthorizedError`를 반환해 주소 자동 검색만 사용할 수 없었습니다.
  TourAPI 장소 검색, 수동 주소 입력과 기획 분석은 계속 동작합니다.
- 재현: `KAKAO_REST_API_KEY`를 설정한 뒤 `GET /api/v1/addresses/search?query=서울 마포구`를 호출합니다.
- 확인한 가설: 키 미설정·키 종류 오류·앱의 지도/로컬 제품 비활성화를 구분했습니다.
- 근거와 원인: Kakao 응답이 해당 앱에서 `OPEN_MAP_AND_LOCAL` 서비스가 비활성화됐다고 명시했습니다.
- 대안: TourAPI 장소 검색 결과의 주소·좌표 사용 또는 주소 직접 입력이 가능합니다.
- 해결 방법: Kakao Developers 콘솔에서 대상 앱의 지도/로컬 API 제품을 활성화하거나, 이미 해당 제품이
  활성화된 팀 소유 앱의 REST API key를 사용합니다. key 값은 저장소와 로그에 남기지 않습니다.
- 검증: 비활성 앱에서는 backend가 403을 503 `UPSTREAM_UNAVAILABLE`로 안전하게 변환하고 frontend의
  다른 기능을 유지했습니다. 이후 지도/로컬이 활성화된 앱으로 바꾸어 backend endpoint와 frontend proxy가
  모두 실제 주소 결과 HTTP 200을 반환하는 것을 확인했습니다.
- 회귀 방지와 남은 위험: 주소 adapter의 성공·실패 fixture 테스트를 유지합니다. 앱 제품 상태나 사용량
  제한이 바뀌면 같은 오류가 재발할 수 있습니다. 다른 프로젝트와 앱을 공유하면 quota·설정 변경의 영향도
  공유되므로 운영 전 사용량과 소유권을 확인합니다.
