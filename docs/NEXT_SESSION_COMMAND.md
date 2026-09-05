# 다음 Codex 세션 작업 명령

아래 요청을 계획만 제시하지 말고 조사, 구현, 검증, 문서화, 로컬 실행까지 끝까지 수행해 줘.

## 목표

`/Users/seongju/heungmap`에서 기획자 기능 담당자가 혼자 완료할 수 있는 모든 잔여 작업을 완성한다.
로그인과 서버 배포는 범위에서 제외한다. 친구가 담당하는 방문객 화면을 대신 구현하지 않는다. 친구의 승인이
필요한 공통 계약 검토는 승인 가능한 자료와 체크리스트까지 준비하고 `공동 검토 대기`로 남긴다.

데이터가 실제로 충분하고 label을 방어할 수 있을 때만 학습 모델을 제품에 연결한다. 데이터가 부족하면
수치나 성능을 만들지 말고, 데이터 게이트 결과와 정확한 차단 조건을 기록한 뒤 모델 이외의 작업을 모두
계속 수행한다.

## 반드시 지킬 운영 규칙

- 저장소의 `AGENTS.md`와 그 안의 Read first 문서를 먼저 읽고 persistent source of truth로 사용한다.
- `$personal-dev-workflow`가 제공되면 사용한다.
- 현재 작업트리의 기존 변경을 보존한다. 관련 없는 파일을 되돌리지 않는다.
- 내가 따로 말하기 전까지 commit, push, PR, merge, 배포를 하지 않는다.
- 로그인, 회원가입, 서버 저장, 운영 서버 배포를 구현하지 않는다.
- UI는 기능 확인에 충분한 간결한 수준으로 유지한다. 전면적인 시각 디자인은 나중 작업이다.
- `.env`, 인증키, token, 원본·가공 데이터, model artifact, cache와 build output을 Git에 넣지 않는다.
- 비밀값을 출력, 문서화, 로그 기록, 화면 캡처, 검색 또는 외부 도구 입력에 포함하지 않는다.
- 기존 `.env`의 key는 값 자체를 출력하지 말고 설정 여부와 실제 HTTP 상태만 확인한다.
- OpenAI 유료 API를 기본 경로로 사용하지 않는다. 로컬 Ollama `qwen3.5:9b`를 사용한다.
- 지역 방문자 수, 상대지수 또는 모델 예측을 특정 축제의 실제 관람객 수라고 표현하지 않는다.
- TourAPI 사용 지점과 원본→파생 feature→예측→LLM 설명의 provenance를 유지한다.
- 외부 계정의 활용신청, CAPTCHA 또는 새로운 key가 꼭 필요하면 공식 신청 화면을 직접 열고, 필요한 항목을
  한 번에 정확히 알려준 뒤 입력이 없어도 할 수 있는 다른 작업을 계속한다.
- 테스트를 약화하거나 실패를 숨기지 않는다. 실제 실행하지 않은 검증을 통과했다고 쓰지 않는다.
- 실질적인 완료 단위마다 기존 work log를 갱신하고, 재사용 가능한 실제 장애는 troubleshooting 문서에 남긴다.

## 현재 확인된 기준 상태

- Next.js 기획자 화면: `http://localhost:3000/planner`
- FastAPI backend: `http://127.0.0.1:8000`
- 기획 입력, browser draft, 수정·복사, 분석 snapshot과 version 이력 구현 완료
- TourAPI `searchKeyword2`, `searchFestival2`, `locationBasedList2` adapter 구현
- Kakao Local 주소·좌표 검색 구현
- 장소·주소·수용인원 미입력과 외부 API 실패 fallback 구현
- 규칙 기반 mock 상대 수요점수와 근거·추천 구현
- Planning Context, structured recommendation, 대안, roadmap, report 구현
- Markdown·JSON 내보내기와 browser PDF 인쇄 구현
- 날짜·지역·규모·장소 수용인원·예산·공간 What-if 구현
- Ollama와 `qwen3.5:9b` 설치 완료
- 실제 로컬 LLM structured report 생성 성공, 약 60초 소요
- backend 29 tests, frontend typecheck·lint·production build 통과 이력 있음
- 실제 학습 데이터, 수집·결합 pipeline, model artifact, SHAP과 실제 prediction 연결은 없음
- Kakao 주소 검색만 있고 Kakao Maps JavaScript 지도 화면은 없음
- 브라우저 E2E test suite는 없음
- 현재 변경은 local worktree에만 있고 Git 전달은 보류 상태

이 상태를 맹신하지 말고 읽기 전용 명령으로 다시 확인한다. 같은 전체 test를 이유 없이 반복하지 말고, 변경
후 focused test와 마지막 full gate를 실행한다.

## 실행 순서

### 1. 사전 점검과 문서 정합성

1. 적용되는 `AGENTS.md`, 시작 문서, 서비스 스펙, 팀 workflow, 공유 스펙, 기획자 workflow, 데이터/API,
   모델 계획, 평가 기준, 결정 기록, OpenAPI catalog와 현재 구현 기록을 읽는다.
2. `git status --short`, 관련 파일 목록, 실행 중인 frontend/backend/Ollama 상태를 확인한다.
3. `.env`의 key 값은 출력하지 않고 필요한 변수의 존재 여부만 검사한다.
4. `PLANNER_WORKFLOW.md`의 외부 LLM API key 미결 문구처럼 현재 Ollama 결정과 어긋난 문서를 수정한다.
5. 구현 상태와 문서 체크박스가 실제 코드 및 검증 결과와 일치하도록 정리한다.

### 2. 데이터 게이트를 실제로 수행

1. 최신 공식 문서에서 다음 두 서비스를 확인한다.
   - 한국관광공사 국문 관광정보 서비스 `searchFestival2`
   - `한국관광공사_빅데이터_지역별 방문자수_GW` 또는 동일 목적의 공식 지역 방문자 데이터
2. 기존 공공데이터포털 key로 지역별 방문자수 API 활용 권한이 있는지 비밀값 없이 실제 smoke call로
   확인한다.
3. 활용신청이 필요하면 공식 신청 페이지를 브라우저에 연다. 사용자에게 서비스명, 눌러야 할 항목과 필요한
   key 변수명만 알려주고 나머지 작업을 계속한다.
4. 재현 가능한 Python 수집 package 또는 scripts를 구현한다.
   - pagination
   - timeout과 제한된 retry
   - 429·5xx·빈 응답 구분
   - 호출 간격과 일일 quota 보호
   - raw response metadata와 retrieved_at 기록
   - resume 가능한 저장
   - encoding/decoding service key 차이 처리
5. 우선 과거 축제 50~100개 이상을 여러 지역·연도에서 수집한다. API가 제공하는 실제 범위가 다르면 그
   범위와 이유를 기록한다.
6. 같은 지역·기간의 방문자 시계열을 수집하거나 공식 DataLab export를 import할 수 있는 adapter를 만든다.
7. 법정동·시군구 코드와 기간을 정규화하고 축제와 방문자 데이터를 결합한다.
8. 다음을 포함하는 machine-readable 품질 보고서와 사람이 읽는 요약을 생성한다.
   - 원본 행 수와 유효 행 수
   - 지역·연도 범위
   - 결합 성공률
   - 결측률과 중복률
   - label 후보별 의미와 단위
   - 지역 집계값을 축제 관람객으로 오해할 위험
   - 잠재적 데이터 누수
   - 학습 가능 여부와 근거
9. 수집 source와 processed output은 ignored 경로에 두되, schema·scripts·작은 synthetic fixture·재현
   명령·품질 기준은 Git 추적 가능한 경로에 둔다.

데이터 게이트 완료 조건은 `searchFestival2`와 방문자 데이터의 실제 응답을 확보하고, 설명 가능한 결합률과
label 의미를 기록하는 것이다. 방문자 데이터가 없으면 게이트를 통과했다고 쓰지 않는다.

### 3. label·feature 결정 자료 준비

1. 다음 label 후보를 실제 데이터로 비교한다.
   - 행사 기간 지역 방문자 수준
   - 평상시 대비 지역 방문자 증가량
   - 평상시 대비 증가율
   - 지역 관광 혼잡 상대지수
2. 각 후보의 집계 단위, 장단점, 누수 위험과 사용자 화면 문구를 표로 만든다.
3. 실제 축제 관람객이라는 표현은 제외한다.
4. 데이터로 가장 방어 가능한 후보를 추천안으로 기록하되, 친구와 공동 승인이 필요하다고 명시한다.
5. feature registry에서 각 feature를 `사용 가능`, `추후 가능`, `누수 위험`, `제외`로 분류한다.
6. 기획 시점에 알 수 없는 개최 후 정보가 학습 feature에 들어가지 않도록 검사 test를 만든다.

### 4. baseline과 실제 모델 구현

데이터 게이트를 통과한 경우에만 진행한다.

1. 학습표 schema v1과 deterministic build command를 구현한다.
2. 지역·월·요일 평균 또는 중앙값 단순 baseline을 구현한다.
3. 현재 규칙 score를 비교 baseline으로 유지한다.
4. LightGBM 회귀 또는 데이터에 더 적합한 작은 tabular model을 구현한다. 불필요한 복잡한 신경망은 쓰지
   않는다.
5. 과거→미래 time split과 행사·지역 group split을 구현한다. random split만으로 성능을 주장하지 않는다.
6. 최소한 MAE, Median AE, RMSLE, baseline 대비 개선과 지역·행사 규모별 error를 기록한다.
7. 가능하면 quantile prediction 또는 검증된 prediction interval을 제공하고 coverage를 측정한다.
8. baseline보다 의미 있게 좋고 error pattern을 설명할 수 있을 때만 model을 채택한다.
9. 학습 config, feature 목록, data version, metric, 생성 시각과 model version metadata를 artifact 옆에 둔다.
10. model artifact는 Git ignore하고 synthetic fixture로 training·inference test를 만든다.
11. 채택된 model에 대해서만 SHAP을 계산한다. 전역 중요도와 단일 예측 영향 요인을 구분한다.

데이터 게이트가 실패하면 synthetic data 성능을 실제 성능처럼 쓰지 않는다. pipeline과 test까지 완성하고
정확한 데이터 차단 조건을 기록한다.

### 5. 실제 prediction API와 기획자 화면 연결

1. 기존 공통 OpenAPI type을 중복하지 않고 실제 model adapter를 backend boundary에 추가한다.
2. 실제 예측 성공 시 다음을 반환한다.
   - `method=machine_learning` 또는 실제 채택 방법
   - `is_mock=false`
   - `model_version`
   - data as-of와 source
   - primary metric과 정확한 unit
   - confidence 또는 prediction interval
   - SHAP 또는 검증된 영향 요인
   - limitations와 out-of-distribution 상태
3. model 미설치·artifact 손상·입력 범위 이탈·추론 오류에는 규칙 baseline으로 전환하고
   `fallback_used=true`와 실제 이유를 표시한다.
4. mock 전용 문구와 badge를 실제 model 상태에 따라 동적으로 바꾼다.
5. Planning Context에 실제 model output을 전달하고 LLM이 값을 변경하거나 실제 관람객 수로 바꾸지 못하게
   backend 검증을 유지한다.
6. What-if가 실제 model을 다시 실행하되 원본 draft를 변경하지 않는지 검증한다.
7. model version이 다른 분석 snapshot과 history가 구분되는지 확인한다.
8. 방문객 화면과 공유할 prediction 계약 변경이 필요하면 새 duplicate type을 만들지 말고 변경안·호환성
   test·검토 체크리스트까지 준비한 뒤 `공동 검토 대기`로 남긴다.

### 6. 지역·장소 정보 완성도 보강

1. 현재 Kakao Local 검색과 TourAPI 장소 선택은 유지한다.
2. 기획자 장소 단계 또는 결과에 작은 Kakao 지도 preview를 추가한다.
   - 선택 행사장 marker
   - 반경 내 주차·숙박·음식점·관광지 marker
   - marker와 목록 선택 동기화
   - source와 거리 표시
   - 지도 SDK 실패 시 기존 목록 유지
3. `KAKAO_JAVASCRIPT_KEY`와 localhost platform 등록이 필요한데 설정이 없으면 값을 요구하지 말고 정확한
   발급·등록 화면을 연 뒤 지도 없는 fallback과 나머지 구현을 완료한다.
4. TourAPI에 없는 공식 수용인원과 대관 가능 여부는 계속 자동 추정하지 않는다.
5. 기상 정보는 최신 공식 API와 데이터 사용 조건을 확인한다. 기획 시점에 의미 있는 forecast 또는 과거
   기후 feature로 방어 가능하면 adapter·provenance·fallback을 구현하고, 아니면 이번 model feature에서
   제외한 이유를 문서화한다.

### 7. quota·cache·성능 보강

1. TourAPI와 Kakao에 다음 cache를 추가한다.
   - 동일 장소 키워드·지역 검색
   - 동일 주소 검색
   - 동일 좌표·반경 주변 장소
   - 동일 지역·기간 행사 목록
2. in-memory local cache로 충분한지 판단하고, 로그인·서버 저장 범위를 만들지 않는다.
3. TTL, 최대 항목 수와 invalidation test를 둔다.
4. 사용자 입력의 연속 검색을 debounce하거나 명시적 버튼 호출로 제한한다.
5. 429, quota, timeout, upstream error와 empty result를 다른 사용자 문구로 표시한다.
6. 실제 API 호출 횟수나 cache hit을 민감정보 없이 개발 로그 또는 진단 metadata로 확인 가능하게 한다.

### 8. 로컬 LLM 품질과 UX 보강

1. Ollama `qwen3.5:9b` 기본 경로, JSON Schema, evidence와 numeric claim 검증, idempotency, timeout과 규칙
   fallback을 유지한다.
2. 대형, 소규모, 대부분 빈 입력, 모순 입력, 강한 고정 제약 scenario를 실제 로컬 model로 반복 평가한다.
3. 다음 위반을 자동 검사하는 eval을 만든다.
   - 입력에 없는 숫자·비용·장소·수용인원 생성
   - 알 수 없는 evidence reference
   - model 수치 변경
   - 실제 관람객 수라고 오해할 표현
   - 고정 제약 위반
   - 대안 개수 불일치
   - 사람 검토 표시 누락
4. 실패한 실제 사례로 prompt·generation schema·post-validation을 최소 수정하고 회귀 fixture를 추가한다.
5. 약 60초 생성 동안 화면에 `데이터 분석 중`, `로컬 AI 보고서 작성 중`, `결과 검증 중` 같은 단계를
   표시하고 중복 제출을 막는다.
6. 취소가 안전하게 가능한 범위와 취소 시 draft·분석 snapshot 보존을 구현한다.
7. model warm/cold latency를 측정해 문서에 기록하되 성능을 과장하지 않는다.

### 9. 브라우저 E2E·접근성·반응형 검증

1. Playwright 기반 E2E 환경을 추가한다.
2. 외부 API는 deterministic fixture 또는 mock server로 테스트하고, 실제 credential smoke는 별도 opt-in
   명령으로 분리한다.
3. 최소 scenario를 자동화한다.
   - 빈 기획→분석→결과
   - 대형 sample
   - 소규모 sample
   - TourAPI 장소 검색과 선택
   - Kakao 주소 선택
   - 장소·주소·수용인원 미입력
   - 날짜·예산 validation 오류
   - TourAPI·Kakao·model·Ollama 실패 fallback
   - 수정 후 새 version
   - What-if
   - Markdown·JSON download
   - PDF print layout 진입
   - reload 후 localStorage draft 복구
4. 키보드 navigation, focus 표시, form label, error focus, aria 상태와 색상만으로 의미를 전달하지 않는지
   확인한다.
5. 모바일과 desktop viewport에서 핵심 흐름을 검사한다.
6. 가능하면 친구의 Windows 환경 재현 체크리스트와 명령을 작성한다. 실제 Windows에서 실행하지 않았다면
   실행했다고 표시하지 않는다.

### 10. 공모전 시연 준비

1. 대형 행사와 소규모 독립 행사 두 demo draft를 실제 화면에서 실행한다.
2. 두 결과가 서로 다른 우선순위와 실행안을 제공하는지 확인한다.
3. TourAPI 사용 화면, 원본 source, 파생값, model output, SHAP, LLM 문장을 따라갈 수 있게 한다.
4. `실제값`, `사용자 입력`, `파생값`, `model 예측`, `가정` badge와 문구를 점검한다.
5. 3분 내 실행 가능한 demo 순서와 예상 질문·정확한 답변을 문서화한다.
6. 로그인·배포가 제외되었다는 사실과 localStorage 한계를 숨기지 않는다.
7. 화면 캡처나 녹화는 필요하면 준비하되 비밀값·개인정보가 보이지 않게 한다.

### 11. 최종 검증과 인계

1. backend focused tests 후 전체 tests를 실행한다.
2. frontend typecheck, lint, production build와 E2E를 실행한다.
3. 실제 TourAPI·Kakao·지역 방문자 API는 key를 노출하지 않고 endpoint별 HTTP 상태, 응답 schema와 최소
   항목 수만 smoke 확인한다.
4. 실제 model inference, model failure fallback, 실제 Ollama report와 Ollama failure fallback을 확인한다.
5. `git diff --check`와 secret scan을 실행한다. `.env`는 permission 600과 Git ignore를 확인한다.
6. planner와 backend를 localhost에 실행하고 실제 URL을 연다.
7. 문서 체크박스, 결정 기록, 구현 기록과 troubleshooting을 실제 결과로 갱신한다.
8. commit, push, PR, merge와 배포는 하지 않는다.

## 최종 보고 형식

작업이 끝나면 다음 순서로 짧고 정확하게 보고한다.

1. 완료한 기획자 기능
2. 데이터 게이트 실제 결과: 행 수·결합률·label 결론
3. 실제 model 채택 여부와 baseline 비교 metric
4. 실제 model·LLM·외부 API smoke 결과
5. backend/frontend/E2E 검증 결과
6. localhost URL
7. 친구의 승인 또는 사용자 계정 작업만 필요한 항목
8. 의도적으로 제외한 로그인·배포·방문객 범위
9. commit·push·PR을 하지 않았다는 확인

“완벽하다”거나 “완료됐다”는 표현은 위 완료 조건을 실제로 검증한 항목에만 사용한다. 외부 데이터나 공동
승인이 없어 막힌 항목은 정확한 blocker 하나와 사용자가 해야 할 최소 행동을 명시하고, 그 밖의 혼자 할 수
있는 작업이 남아 있으면 멈추지 말고 계속 진행한다.
