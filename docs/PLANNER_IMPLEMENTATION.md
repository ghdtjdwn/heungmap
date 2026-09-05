# 기획자 기능 구현 상태

## 현재 범위

로그인·서버 배포를 범위에서 제외하고, 검증에서 채택되지 않은 자체 수요 모델만 mock으로 둔 기획자 로컬
흐름입니다. 데이터 게이트는 통과했지만 LightGBM 일반화가 부족해 제품에는 연결하지 않았습니다. 상세
입력은 브라우저에 저장하고 공통 OpenAPI 계약에 포함된 값만 FastAPI 분석 endpoint로 전달합니다. 실제
판정은 [`DATA_GATE_REPORT.md`](DATA_GATE_REPORT.md)에 있습니다.

## 구현된 흐름

1. 기획 목록에서 빈 기획 또는 대형·소규모 대표 scenario를 시작합니다.
2. 기획자 상태, 행사 목표, 이용객·티켓, 일정·지역, 장소·규모, 프로그램·예산·홍보·운영·안전, 제약을 단계형 form으로 작성합니다.
   장소명은 TourAPI `searchKeyword2`, 주소와 좌표는 Kakao Local 주소 검색으로 자동 입력할 수 있습니다.
   장소·주소·공식 수용인원을 비우면 필요한 규모·접근성·시설 조건과 확인 순서를 결과에서 안내합니다.
3. 입력을 자동 저장하고 이전 단계 이동, 수정, 복사본 생성과 전체 검토를 수행합니다.
4. `POST /api/v1/planner/analyses`로 분석 snapshot을 보내 규칙 기반 mock 상대 수요점수, 영향 요인, 우선 추천과 TourAPI 근거를 받습니다.
5. Planning Context를 `POST /api/v1/planner/recommendations`에 한 번 전달해 실제 LLM 구조화 보고서를 생성합니다. LLM을 사용할 수 없으면 같은 근거의 규칙 보고서로 자동 전환합니다.
6. 보고서, 근거·출처, LLM 또는 fallback 표시, Planning Context와 분석 version 이력을 확인합니다. Kakao
   JavaScript 키와 domain을 사용해 선택 장소와 TourAPI 주변 장소를 지도·목록으로 함께 탐색합니다.
7. 날짜·지역·규모·장소 수용인원·예산·공간을 바꾼 What-if를 원본과 비교합니다.
8. 보고서를 Markdown·PDF로, 전체 결과와 Planning Context를 JSON으로 내보내고 요약을 복사합니다.

## 실패와 한계 처리

- 자체 수요 결과는 `MODEL MOCK`, `is_mock=true`, 낮은 신뢰도와 해석 한계를 항상 표시합니다.
- TourAPI key·좌표·응답이 없으면 주변 근거만 `unavailable`로 표시하고 입력, mock score와 규칙 보고서를 유지합니다.
- 장소·주소 검색 key나 외부 응답이 없으면 검색 오류만 표시하고 수동 입력과 분석 흐름을 유지합니다.
- TourAPI 장소 후보에는 공식 수용인원이 없으므로 값을 생성하지 않으며 대관 가능 여부와 함께 별도 확인하도록 표시합니다.
- frontend는 일시 오류나 timeout을 한 번 재시도하며 최종 실패 시에도 입력을 로컬에 보존합니다.
- TourAPI와 Kakao Local의 성공 응답은 process-local TTL LRU cache로 재사용하며 오류는 cache하지 않습니다.
- LLM 요청은 분석 버튼을 눌렀을 때 한 번만 실행하고 자동 재시도하지 않습니다. backend는 idempotency,
  100KB Context 제한, provider별 timeout, strict JSON Schema, 대안 개수, evidence reference와 입력에 없는
  숫자 생성을 검증합니다. OpenAI를 선택한 경우 provider 저장을 끕니다.
- 로컬 Ollama 미실행, model 미설치, timeout, upstream 오류나 잘못된 출력은 분석 실패로 번지지 않고 규칙
  보고서와 화면 경고로 전환됩니다.
- 지역 방문수요나 상대지수를 특정 행사의 실제 관람객 수로 표시하지 않습니다.

## 데이터·검증 현황

- 실제 TourAPI 축제 원본 688건과 지역 방문자 464,092행을 수집했습니다. 일별 기초지자체 154,706행으로
  정규화하고 행사 중복을 제거해 514건·76.37%를 결합했습니다.
- 시간 분할 410/104에서 지역 중앙값 baseline MAE 0.077481, LightGBM MAE 0.090058로 16.23%
  악화됐습니다. 미관측 지역 5-fold MAE는 baseline 0.103730, LightGBM 0.100590이었습니다.
- 시간 일반화 채택 기준을 통과하지 않아 실제 model과 SHAP은 제품에
  연결하지 않았습니다.
- 수집·재개·정규화·결합·품질 보고와 누수 검사는 구현하고 fixture로 검증했습니다.
- Playwright는 7개 test로 대형·소규모, 검색·실패 fallback, validation, version·What-if,
  localStorage, 내보내기·인쇄, 키보드와 desktop·mobile 흐름을 검사합니다.
- 최종 병합 전 backend test 41개, frontend typecheck·lint·production build와 Playwright 7개가
  통과했습니다.
- 실제 로컬 `qwen3.5:9b` 평가에서 대형, 소규모, 대부분 미입력, 수용규모 모순, 강한 고정 제약의 5개
  scenario가 최종 validator를 통과했습니다. 응답 시간은 31.054–51.978초, 평균 41.746초였습니다. 첫 full
  run의 고정 제약 문장 오탐을 수정한 뒤 해당 scenario만 다시 실행해 통과했으므로 한 번의 동시 benchmark로
  해석하지 않습니다. 생성문은 저장하지 않고 상태·지연·검증 진단만 ignored report에 기록했습니다.
- 공통 prediction·label 계약은 승인 자료가 준비됐으며 상대 담당자와 **공동 검토 대기**입니다.

## 실제 완료까지 남은 외부 조건

| 항목 | 코드 상태 | 외부 조건 |
| --- | --- | --- |
| 장소명·주변 관광정보 | TourAPI adapter, 실패 fallback, 실제 backend·frontend proxy 200 확인 | 완료 |
| 주소·좌표 | Kakao Local adapter, 수동 입력 fallback, 실제 backend·frontend proxy 200 확인 | 완료. 기존 앱 quota와 제품 상태 유지 필요 |
| 자체 수요 모델 | 514건 학습표, baseline·LightGBM 시간/group 평가 완료, 제품은 mock 유지 | 시간 분할 성능 개선 feature 확보 후 재평가 |
| LLM 기획 추천 | Ollama `qwen3.5:9b` 기본 adapter와 선택적 OpenAI adapter, 공통 endpoint, schema·근거 검증, idempotency·timeout·규칙 fallback 구현 | 로컬 model 설치·실제 생성 smoke test 완료 |
| Kakao 지도 | 선택 장소 marker, TourAPI 주변 marker·목록 동기화와 목록 fallback 구현 | JavaScript 키·localhost SDK domain 등록 완료, 실제 브라우저 smoke 확인 |
| 로그인·서버 저장 | 구현 범위에서 제외 | browser `localStorage`만 사용 |
| 서버 배포 | 구현 범위에서 제외 | localhost 실행과 재현 절차만 유지 |

## 작업 기록

### 2026-09-06 — 데이터 게이트·지도·cache·LLM eval·E2E

- 최초에는 방문자 API 권한이 없어 결합 0건이었지만 승인 키 적용 후 2025–2026 축제·방문자를 수집해
  중복 제거 후 514건·76.37%로 결합했습니다.
- 실제 LightGBM은 시간 MAE가 baseline보다 16.23% 나빠 채택하지 않았고,
  채택 모델이 없으므로 SHAP도 계산하지 않았습니다.
- 재개 가능한 데이터 수집·결합·품질 보고, 외부 조회 TTL LRU cache, Kakao 지도와 목록 fallback,
  LLM 제약 검증·취소 상태, Playwright E2E와 3분 시연 자료를 추가했습니다.
- 공통 계약 승인만 외부 작업으로 남기고 로그인·배포·방문객 화면은 범위에서 제외했습니다. 이번
  작업에서는 commit, push, PR 변경과 배포를 수행하지 않았습니다.

### 2026-09-06 — 기획자 로컬 흐름 commit·push와 PR 갱신

- 공통 계약·구현 문서, FastAPI 분석·외부 API·로컬 LLM backend, Next.js 기획자 화면을 각각 논리적인
  commit으로 분리했습니다: `5ae955c`, `7859b36`, `03e23ff`.
- push 직전 Git 사용자 email의 GitHub 계정 연결, 인증 계정과 저장소 소유자 일치, staged·commit 대상의
  secret pattern, `.env` permission 600과 Git ignore 상태를 확인했습니다.
- backend test 29개와 frontend typecheck·lint·production build가 통과한 상태로
  `feat/planner-prototype`을 push했습니다.
- 기존 PR #16의 제목과 본문을 실제 구현 범위, 검증 결과, mock model 한계와 공동 검토 항목에 맞게
  갱신했습니다.
- PR merge와 배포는 수행하지 않았습니다. 다음 작업 단위는 데이터 게이트와 실제 model pipeline입니다.

### 2026-09-06 — 다음 세션 전체 잔여 작업 인계

- 기획자 담당자가 혼자 완료할 수 있는 데이터 게이트, 실제 모델, 제품 연결, 지도·날씨 판단, cache,
  로컬 LLM 평가, E2E·접근성, 시연과 최종 검증 작업을 실행 순서와 완료 조건으로 정리했습니다.
- 로그인·서버 배포·방문객 화면은 제외하고, 공통 계약은 검토 자료까지만 준비하며 친구 승인 전 완료로
  표시하지 않도록 범위를 명확히 했습니다.
- 다음 세션용 실행 명령은 `docs/NEXT_SESSION_COMMAND.md`에 저장했습니다.
- 이번 인계 작업에서는 commit, push, PR 변경과 배포를 수행하지 않았습니다.

### 2026-09-06 — 장소·주소 검색과 빈칸 추천 안내

- 로그인과 서버 배포를 현재 완료 범위에서 제외하고 localhost 제품 흐름을 기준으로 확정했습니다.
- TourAPI `searchKeyword2` 장소 후보와 Kakao Local 주소·좌표 검색을 공용 endpoint로 연결했습니다.
- 장소명·주소 검색 결과 선택, 좌표 자동 입력, 검색 실패 시 수동 입력 fallback을 장소 단계에 추가했습니다.
- 장소와 공식 수용인원을 비워도 어떤 추천을 받는지 필드별 안내하고, 확인되지 않은 수용인원은 자동 생성하지 않게 했습니다.
- backend test 19개와 frontend typecheck·lint·production build를 실행해 통과했습니다. 초기 검증에서는
  key가 없어 실제 외부 API 호출을 실행하지 못했습니다.
- 이후 로컬 key를 설정해 TourAPI `searchKeyword2`의 실제 장소 결과와 frontend proxy의 HTTP 200을
  확인했습니다. 처음 사용한 Kakao 앱은 지도/로컬 제품 비활성화로 403을 반환했지만, 지도/로컬이 이미
  활성화된 앱의 REST key로 교체한 뒤 backend와 frontend proxy 모두 실제 주소 결과 HTTP 200을 확인했습니다.
- 변경은 로컬 작업트리에만 있으며 commit, push, PR 변경과 배포는 수행하지 않았습니다.

### 2026-09-06 — 실제 LLM 추천 경로와 안전한 fallback

- `POST /planner/recommendations` 공통 계약과 OpenAI Responses API adapter를 추가했습니다.
- Structured Outputs, `store=false`, 100KB 입력 제한, 45초 timeout, 요청 idempotency와 응답의
  `evidence_ref`·대안 개수·사람 확인 표시·입력에 없는 숫자를 검증합니다.
- frontend 분석 흐름이 실제 LLM 결과를 로컬 draft에 보관하고, 미설정·오류·timeout·계약 위반에는 규칙
  보고서와 원인을 저장하도록 연결했습니다. 결과·Markdown·JSON에서 생성 방식을 구분합니다.
- backend test 26개와 frontend typecheck·lint·production build를 실행해 통과했습니다. 실제 LLM provider
  호출은 가장 저렴한 `gpt-5-nano`로 실행했으나 provider가 429 `credit_balance_exhausted`를 반환했습니다.
- 실행 중인 localhost에서 planner HTML 200, 새 OpenAPI path 노출, LLM 미설정 503 fallback 계약을
  확인했고 TourAPI 장소 검색과 Kakao 주소 검색의 실제 frontend proxy 응답도 각각 HTTP 200을 재확인했습니다.
- 변경은 로컬 작업트리에만 있으며 commit, push, PR 변경과 배포는 수행하지 않았습니다.

### 2026-09-06 — 비용 없는 로컬 LLM으로 전환

- 16GB Apple M1 Pro에서 실행 가능한 최신 후보를 비교해 Ollama `qwen3.5:9b`를 기본 LLM으로 선택했습니다.
  model 크기가 장비 메모리를 넘는 27B는 제외하고, 한국어를 포함한 다국어 instruction 지원과 structured
  output을 우선했습니다.
- provider adapter가 Ollama `/api/chat`과 OpenAI Responses를 같은 내부 요청·응답 계약으로 처리하도록
  변경했습니다. 로컬 요청은 JSON Schema, `temperature=0`, 제한된 context·출력 길이와 명시적인 no-thinking
  설정을 사용합니다.
- 로컬 실행 timeout을 반영해 backend와 frontend 제한을 조정하고, Ollama 요청 형식과 provider metadata를
  검사하는 회귀 test를 추가했습니다.
- Ollama application과 `qwen3.5:9b`를 로컬에 설치하고 실제 구조화 기획 보고서가 약 60초 안에
  `generation_mode=llm`으로 생성되는 것을 확인했습니다.
- Pydantic schema의 문자열 길이 제약과 Ollama grammar parser의 호환 문제를 generation schema adapter로
  해결했습니다. 전체 application 계약은 생성 뒤 원본 Pydantic 검증으로 유지합니다.
- 30초 안팎에서 끊기는 Next.js 개발 rewrite를 피하도록 LLM 호출만 localhost FastAPI로 직접 보내고,
  허용된 frontend origin의 CORS preflight를 검증했습니다.
- backend test 29개와 frontend typecheck·lint·production build를 실행해 통과했고, planner 화면과 backend
  health가 실행 중인 localhost에서 각각 HTTP 200임을 확인했습니다.
- 유료 OpenAI key는 로컬 환경에서 제거했으며 OpenAI adapter는 선택 기능으로만 유지합니다.
- 변경은 로컬 작업트리에만 있으며 commit, push, PR 변경과 배포는 수행하지 않았습니다.

### 2026-09-05 — 로그인 전 기획자 로컬 흐름 완성

- 단계형 상세 입력, 브라우저 draft, 분석 snapshot, 규칙 진단, 보고서, Planning Context, version 이력과 What-if를 구현했습니다.
- FastAPI의 mock prediction, TourAPI adapter, unavailable fallback, validation과 idempotency를 연결했습니다.
- backend test 13개, frontend typecheck·lint·production build, 로컬 브라우저 대형 scenario와 What-if 흐름을 실행해 확인했습니다.
- 변경은 로컬 작업트리에만 있으며 commit, push, PR 변경, 배포는 수행하지 않았습니다.
- 남은 항목은 데이터 게이트 이후 학습 모델·SHAP과 상대 담당자의 공통 contract 검토입니다.
  로그인·서버 배포는 구현하지 않습니다.
