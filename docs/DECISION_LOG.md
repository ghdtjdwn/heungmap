# 의사결정 기록

## D1. 축제 수요 예측을 첫 문제로 선택

- 지역·기간별 방문자 시계열과 TourAPI 축제 정보를 결합해 기획 단계의 수요 불확실성을 줄입니다.
- 핵심 위험은 축제 단위 label의 품질이므로 모델 개발보다 데이터 검증을 먼저 수행합니다.
- label을 방어하기 어렵다면 동일한 파이프라인을 지역별 관광 혼잡 예측에 재사용합니다.

## D2. 단계적 전달

- 데이터 조립, 모델과 웹 화면의 실패 조건을 분리하기 위해 단계별 완료 조건을 둡니다.
- 규칙 기반 baseline과 최소 사용자 흐름을 먼저 완성하고, 검증 결과가 있을 때만 학습 모델과 설명 기능을 추가합니다.
- 외부 API나 선택 기능이 실패해도 기본 탐색과 수요 지표는 동작해야 합니다.

## D3. 기획자와 방문객을 하나의 예측 결과로 연결

- 기획자 입력은 수요 예측에 사용되고, 공개된 축제 정보는 방문객 탐색 화면으로 이어집니다.
- 두 화면이 동일한 데이터 정의와 예측 결과를 사용해 지표 불일치를 줄입니다.

## D4. 서비스 이름

- `흥할지도 (HeungMap)`는 축제의 수요 가능성과 지도 기반 탐색이라는 두 제품 기능을 함께 나타냅니다.

## D5. 리셀 가격 예측 제외

- 신뢰할 수 있는 공개 데이터가 부족하고 불법 거래를 조장하는 기능으로 오해될 수 있습니다.
- 대신 예측 방문자 수에서 계산한 티켓 수요 지표를 제공하고 계산 근거를 함께 표시합니다.

## D6. 웹 단일 클라이언트

- 예측 대시보드와 지도 탐색을 같은 화면 흐름에서 제공하기 위해 웹을 우선합니다.
- 별도 모바일 앱은 사용자 요구와 운영 필요가 확인될 때 검토합니다.

## D7. 데이터 부족 시 범위 전환

- 축제별 label 결합률이나 표본 수가 기준에 미달하면 지역·기간별 관광 혼잡 예측으로 전환합니다.
- 방문자 수집, 지역 코드 정규화와 기간 집계는 두 문제에서 재사용합니다.

## D8. 심사기준을 기능 우선순위로 사용

- 1차 심사는 서비스 구현성 30점, 서비스 기획력 30점, 데이터 활용 적절성 20점, 서비스 발전성 20점으로 평가됩니다.
- 최종 심사는 서비스 적정성 30점, 서비스 완성도 30점, 서비스 실용성 25점, 발표점수 15점으로 평가됩니다.
- 과제 9번 핵심 흐름의 완결성과 안정성, TourAPI의 핵심 활용, 예측의 타당성과 독창성, 사용 편의와 확장성 순으로 개발 우선순위를 판단합니다.
- 기능을 시작하기 전에 기여할 심사항목과 완료 조건을 적고, 기반 제품 완성을 늦추는 선택 기능은 뒤로 미룹니다.
- 세부 대응과 제출 전 점검 항목은 `EVALUATION_CRITERIA.md`에서 관리합니다.

## D9. 이용객과 규모별 기획자를 대상 사용자로 정의

- 이용객은 축제뿐 아니라 콘서트와 행사를 방문하며 혼잡도, 티켓 수요와 주변 이동 정보를 필요로 합니다.
- 기획자는 지자체·공연기획사·행사 대행사 등 대형 행사 주체와, 홍대 클럽 공연처럼 자본과 정보가 부족한 상태에서 직접 기획하는 소규모 독립 기획자·가수를 모두 포함합니다.
- 대형 기획자에게는 수요·장소·편의시설 보완 근거를, 소규모 기획자에게는 제한된 예산 안에서 시기·장소·규모의 위험을 비교할 수 있는 의사결정 지원을 제공합니다.
- 공모전의 초기 데이터와 제품 범위는 지정과제 9번 및 TourAPI와 직접 연결되는 축제·지역 행사로 유지합니다.
- 콘서트·클럽 공연은 공연별 데이터와 label의 타당성을 별도로 검증한 뒤 확장하며, 검증 전에는 현재 지원 범위나 예측 성능으로 주장하지 않습니다.

## D10. 2인 역할을 기획자 기능과 사용자 기능으로 분리

- 한 명은 기획 조건 입력부터 수요 결과·근거·보완점까지 기획자 흐름을 end-to-end로 책임집니다.
- 다른 한 명은 행사 탐색부터 캘린더·지도·상세·주변 정보까지 사용자 흐름을 end-to-end로 책임집니다.
- 사용자 기능의 정보구조와 상호작용은 EVENT-US의 공개 행사 캘린더·행사 지도를 주요 기준으로 삼습니다.
- EVENT-US 조사는 담당자 확정 후 시작하며, 현재는 사용자 요청에 따라 진행하지 않았습니다.
- 공개 동작은 벤치마킹하되 비공개 architecture나 source code를 안다고 가정하지 않고, 제3자 brand·asset·문구·code를 복사하지 않는 독립 구현을 원칙으로 합니다.
- 행사·장소·수요 결과·탐색 filter·출처·오류 schema는 두 흐름이 공유하므로 한 명이 계약을 관리하고 다른 한 명이 검토합니다.

## D11. 지역 baseline과 행사 uplift를 결합한 공유 예측 엔진

- 핵심 AI는 LLM이 아니라 행사 전 정보로 수요와 위험을 계산하는 예측 엔진입니다.
- 먼저 해당 지역·시기의 평상시 수요 baseline을 계산하고, 행사 특성으로 인한 추가 수요 uplift를 결합합니다.
- label은 공식 관람객·입장 집계, 예매·판매량, 지역 방문수요 증가분, 설명 가능한 합성 score 순으로 검토합니다.
- 지역 방문자 자료만 확보되면 특정 행사 관람객 수로 표현하지 않고 방문수요 증감률 또는 상대 score로 제공합니다.
- 입력 후보는 넓게 기록하되 가용성·재현성·데이터 누수·품질·사용자 가치를 검증한 항목만 실제 학습에 사용합니다.
- 단순·규칙 baseline보다 시간·group 분할 평가에서 의미 있게 좋아진 경우에만 LightGBM을 제품 기본 모델로 채택합니다.
- 기획자와 사용자 화면은 같은 prediction 계약, model version, 출처와 한계 설명을 공유합니다.
- 세부 입력·출력 후보와 학습 순서는 `MODEL_PLAN.md`에서 관리합니다.

## D12. 기획자 입력·예측·LLM을 순서대로 분리

- 기획자는 단계형 form에서 선택지, 기타 직접 입력, 아직 모름과 추천받기를 사용해 행사 조건을 작성합니다.
- 시스템은 입력을 검증한 뒤 TourAPI·관광 데이터랩 등 근거와 자체 수요 예측 모델 결과를 먼저 계산합니다.
- LLM은 구조화된 입력·근거·예측 결과를 이용해 기획안, 대안, 우선 보완점과 실행 체크리스트를 생성합니다.
- LLM은 예측 모델의 수치를 변경하거나 장소·비용·법규·성과를 근거 없이 생성하지 않습니다.
- 사실·사용자 입력·파생값·모델 예측·가정·추천을 구분하고, 추천에는 근거·신뢰도와 사람 확인 필요 여부를 표시합니다.
- model이나 LLM이 실패해도 입력 초안, 규칙 baseline과 검증된 근거는 유지합니다.
- 전체 입력·출력 후보와 기획자 담당 범위는 `PLANNER_WORKFLOW.md`에서 관리합니다.

## D13. 역할별 end-to-end 소유권과 shared-first 시작 순서

- 역할을 정한 뒤 기획자와 사용자 담당은 각 사용자 흐름의 화면, 연동, 오류, 테스트와 문서를 끝까지 책임집니다.
- 기능 구현 전에 두 명이 TourAPI·지역 방문자 데이터 게이트와 공통 `Event`·`Prediction`·오류 계약 v0.1을 함께 검증합니다.
- 기획자 담당의 첫 결과는 LLM이 없는 mock 기반 입력→진단 흐름이고, 사용자 담당의 첫 결과는 공개 EVENT-US 조사와 mock 기반 캘린더→지도→상세 흐름입니다.
- 두 기능 PR은 공통 contract v0.1 확인 이후 병렬로 진행하며, 계약 변경은 별도 shared PR과 상대 담당자 검토를 거칩니다.
- 역할 직후의 작업 순서와 파일 소유권은 `00_START_HERE.md`, 사용자 담당의 상세 범위는 `VISITOR_WORKFLOW.md`에서 관리합니다.

## D14. 역할 담당자 확정

- 홍성주는 기획자 기능을 맡아 기획 조건 입력부터 수요 결과·근거·보완점까지 end-to-end로 책임집니다.
- 박지성은 사용자 기능을 맡아 행사 탐색부터 캘린더·지도·상세·주변 정보까지 end-to-end로 책임집니다.
- 공유 데이터·예측 계약 관리자와 통합 검토자는 후속 합의로 정합니다.
- 역할이 확정됐으므로 박지성은 `VISITOR_WORKFLOW.md`에 따라 EVENT-US 공개 화면 조사를 시작할 수 있습니다.

## D15. OpenAPI 3.1 기반 단일 공통 계약

- 기획자와 사용자 서비스의 공통 HTTP·JSON 계약은 `contracts/openapi.yaml` 한 곳에서 version `0.1.0`으로 관리합니다.
- OpenAPI 3.1.0과 JSON Schema 2020-12 호환 schema를 사용해 FastAPI·Pydantic과 이후 TypeScript client 생성을 연결합니다.
- 행사, 장소, 주변 장소, 검색 filter, 예측, 근거와 오류 field를 공통화하고 role별 중복 type을 만들지 않습니다.
- 예측은 `official_attendance`, `ticket_demand`, `regional_visit_demand`, `relative_demand_score`를 구분하며 데이터 게이트 전에는 공식 관람객 예측을 반환하지 않습니다.
- 예측할 수 없음은 정상적인 `unavailable` 상태로 반환해 행사 탐색을 유지하고, HTTP 오류는 RFC 9457 `application/problem+json` 형식을 사용합니다.
- 최신 OpenAPI 3.2보다 현재 FastAPI와 client tooling이 직접 지원하는 3.1.0의 호환성과 팀 유지보수성을 우선했습니다.

## D16. Next.js·FastAPI와 개인 Ubuntu 서버 단일 배포

- frontend는 Next.js App Router·TypeScript, backend는 FastAPI·Pydantic으로 확정합니다.
- Streamlit은 data spike에는 빠르지만 목표 캘린더·지도·반응형 UI와 URL 상태 구현에 제약이 있어 제품 frontend에서 제외합니다.
- 개인 Ubuntu 서버는 Nginx 뒤에 Next.js와 FastAPI를 같은 origin으로 제공하는 단일-instance 배포 후보로 사용합니다.
- 비공개 기록에는 접속 정보가 있으나 CPU·RAM·저장공간과 설치 service는 확인되지 않아 server 사전점검 통과를 배포 go 조건으로 둡니다.
- 첫 배포는 systemd를 사용하고 Docker·Redis·PostgreSQL은 실제 운영 필요가 확인되기 전에는 추가하지 않습니다. 저장이 필요하면 SQLite부터 검토합니다.
- 세부 구조와 보안·운영 점검은 `DEPLOYMENT.md`에서 관리합니다.

## D17. 로그인 전 기획자 초안은 브라우저에만 보관

- 로그인 구현 전에는 기획자 초안과 분석 결과를 browser `localStorage`에 저장하고 server에는 영구
  저장하지 않습니다.
- 자동 저장, 수정, 복사와 결과 재확인은 같은 browser 안에서 제공하되 다른 기기 동기화·공유·공개를
  약속하지 않습니다.
- 자체 수요 모델 연결부는 공통 `Prediction` 계약을 따르는 mock 상대지수로 격리하고 `is_mock=true`,
  낮은 신뢰도와 한계를 항상 표시합니다. 데이터 게이트와 baseline 비교를 통과하기 전에는 실제 관람객
  예측으로 표현하지 않습니다.
- TourAPI 키나 장소 좌표가 없거나 외부 API가 실패하면 주변 근거만 `unavailable`로 반환하고 입력,
  규칙 추천과 보고서는 유지합니다.
- 서버 draft 저장은 인증·개인정보·삭제 정책과 공유 요구가 합의된 뒤 별도 결정으로 추가합니다.

## D18. 상세 기획 입력은 공통 계약 밖의 로컬 Planning Context로 관리

- 공통 `EventDraft`와 `Prediction` 의미는 변경하지 않고, 팀·이용객·프로그램·티켓·예산·홍보·운영·안전·접근성 상세 입력은 기획자 전용 `PlanningDetails`로 브라우저에 저장합니다.
- 분석 시 상세 입력과 공통 `PlannerAnalysisResponse`를 `Planning Context 1.0`으로 조립해 출처, 값 종류, 단위, 한계와 누락 정보를 함께 내보냅니다.
- 공유 LLM endpoint와 제공자가 확정되기 전에는 외부 LLM을 호출하지 않고 규칙 template을 사용합니다. 자체 수요 결과만 `model_mock=true`로 표시하며 규칙 문장이 새로운 예측 수치를 만들지 않게 합니다.
- 분석 실행 때 최대 20개의 로컬 version snapshot을 남깁니다. What-if는 원본을 수정하지 않고 날짜·지역·규모·장소 수용인원·예산·공간 조건을 임시 비교합니다.
- 상세 입력을 공통 OpenAPI에 추가하는 안은 사용자 화면과 model adapter까지 영향을 주므로 공동 계약 검토 전에는 채택하지 않습니다.

## D19. 장소 후보와 주소 검색은 공용 backend 계약으로 제공

- 장소명 후보는 필수 관광 데이터 활용을 분명히 하기 위해 TourAPI `searchKeyword2`로 검색하고 공용
  `Venue`의 이름·주소·좌표에 매핑합니다.
- TourAPI 검색 결과에 없는 공식 수용인원, 대관 가능 여부와 시설 상태는 추정하지 않으며 장소 운영자
  확인 전에는 빈 값으로 둡니다.
- 주소는 선택한 Kakao 지도 스택과 같은 Kakao Local REST API를 backend에서 호출해 도로명·지번 주소와
  좌표를 반환합니다. REST API 키는 browser bundle에 노출하지 않습니다.
- 두 검색은 기획자 전용 중복 type 대신 `/venues/search`, `/addresses/search` 공용 endpoint와 기존
  `Venue`, `Coordinates`, `SourceRef`, `Problem` 계약을 재사용합니다. 상대 담당자의 계약 검토 전에는
  로컬 변경으로 유지합니다.
- 장소가 미정이면 존재하지 않는 후보를 생성하지 않고 목표 인원에 필요한 수용 규모, 접근성, 시설과
  실제 후보 확인 순서를 추천합니다. 검색 실패 시에도 수동 입력과 분석 흐름은 유지합니다.

## D20. 현재 제품 범위에서 로그인과 서버 배포 제외

- 현재 완료 기준은 두 팀원이 macOS와 Windows에서 재현할 수 있는 localhost 제품 흐름입니다.
- 로그인, 계정, server-side draft 저장, 기기 간 동기화와 운영 서버 배포는 구현하지 않습니다.
- 기획자 초안과 분석 결과는 기존 결정대로 browser `localStorage`에만 저장하며 화면에서 이 한계를
  명시합니다.
- `DEPLOYMENT.md`와 D16은 이전에 검토한 후보 구조의 기록으로만 남기고 현재 구현·검증 범위에는 적용하지
  않습니다.
- 제외 결정은 학습 모델을 제외한 기획자 입력, 실제 외부 API, LLM 추천, 오류 fallback과 로컬 검증 범위를
  줄이지 않습니다.

## D21. 실제 LLM 보고서는 공급자 adapter로 격리하고 로컬 Ollama를 기본 사용

- 공통 HTTP 계약에 `POST /planner/recommendations`를 추가하고 frontend는 분석 완료 뒤 Planning Context와
  규칙 추천을 한 번 전달합니다.
- SDK 의존성을 추가하지 않고 기존 `httpx`로 provider API를 호출합니다. provider, base URL과 model은
  환경변수로 주입해 application 계약과 특정 model 이름을 분리합니다.
- 16GB Apple Silicon 개발 장비에서는 Ollama `qwen3.5:9b`를 기본으로 사용합니다. 같은 계열 27B는 model
  크기만 16GB를 넘고 운영체제·application 메모리가 추가로 필요해 제외했습니다. 더 오래된 12B·14B보다
  최신 다국어 instruction model을 선택하되 실제 품질은 기획 scenario로 계속 평가합니다.
- 선택 근거는 Qwen의 공식 9B model card, Ollama 공식 model registry와 macOS·structured output 문서로
  확인했습니다: <https://huggingface.co/Qwen/Qwen3.5-9B>, <https://ollama.com/library/qwen3.5/tags>,
  <https://docs.ollama.com/macos>, <https://docs.ollama.com/capabilities/structured-outputs>.
- Ollama의 JSON Schema `format`과 OpenAI Responses의 Structured Outputs를 같은 Pydantic 응답 계약으로
  검증합니다. backend는 100KB Context 제한, provider별 timeout, idempotency, 요청한 대안 개수, 입력에
  존재하는 `evidence_ref`와 입력에 없는 숫자를 생성했는지 검증합니다. OpenAI 요청은 `store=false`입니다.
- 자동 LLM 재시도는 중복 비용과 대기시간을 피하기 위해 하지 않습니다. 미설정·timeout·upstream 오류나
  잘못된 출력이면 frontend가 기존 규칙 추천으로 보고서를 만들고 생성 방식을 명시합니다.
- 자유 형식 text endpoint는 출력 검증이 약해 제외했고, provider SDK 직접 결합은 dependency와 교체 비용을
  늘려 제외했습니다. OpenAI는 유료 credit을 쓸 수 있을 때 선택하는 adapter로 유지합니다.
- 학습된 자체 수요 model만 계속 mock이며, LLM은 그 상대지수를 변경하거나 실제 관람객 수로 해석하지
  않습니다. 로컬 LLM도 자체 수요 예측 model을 대신하지 않습니다.

## D22. 데이터 게이트와 모델 채택을 분리해 판정

- 2026-09-06 `searchFestival2` 축제 원본 688건과 지역 방문자 464,092행을 수집해 중복 제거 후
  514건·76.37%를 결합했습니다.
  최소 50건·70%인 데이터 게이트는 통과했습니다.
- label 후보는 직전 28일 중앙값 대비 행사 기간 기초지자체 방문수요 증가율입니다. 이는 특정 축제
  관람객이 아니며 최종 이름·단위·UI 표현은 공동 승인 대상으로 남깁니다.
- 2025–2026 시간 분할에서 LightGBM MAE는 지역 중앙값 baseline보다 16.23% 높고 RMSE도 나빴습니다.
  미관측 지역 5-fold 평균 MAE는 소폭 낮았지만 시간 일반화 실패를 상쇄하지 못합니다.
- 따라서 학습·평가 pipeline과 실제 metric은 보존하되 model artifact를 제품에 연결하지 않습니다.
  SHAP은 채택 모델에만 적용하므로 계산하지 않고 규칙 mock과 실패 fallback을 유지합니다.

## D23. 외부 조회 cache, 지도 fallback과 결정론적 E2E를 로컬 baseline에 포함

- TourAPI와 Kakao Local의 동일 조회는 process-local TTL LRU cache를 사용해 quota와 반복 지연을 줄입니다.
  cache는 원본·가공 데이터나 인증키를 디스크에 저장하지 않고 오류 응답도 저장하지 않습니다.
- Kakao Maps JavaScript 키와 localhost domain을 설정하고 선택 장소와 TourAPI 주변 장소가 실제 지도와
  목록에서 동기화되는 것을 확인했습니다. 키나 SDK가 없으면 출처·거리 목록을 그대로 제공합니다.
- Playwright는 외부 API를 fixture로 고정해 입력, 검색, 실패 fallback, version, What-if, 내보내기,
  localStorage, 키보드와 desktop·mobile 흐름을 반복 검증합니다. 실제 credential smoke는 별도 실행합니다.
- 로컬 LLM은 실제 5개 대표 scenario에서 구조화 계약·숫자·근거·제약·사람 검토 검증을 통과했고
  31.054–51.978초가 걸렸습니다. 위반 출력은 자동 수정하지 않고 규칙 fallback을 유지합니다.
- 지도 관련 공통 HTTP type은 새로 만들지 않고 기존 `Coordinates`, `NearbyPlace`, `SourceRef`를 재사용하며
  상대 담당자 검토 상태는 `공동 검토 대기`입니다.

## 미결 사항

- 지역 방문수요 증가율 label 이름·단위·UI 표현의 공동 승인
- 다년 데이터 확보 뒤 모델 채택 기준 재평가
