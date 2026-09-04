# 흥할지도 작업 시작 안내

이 문서는 역할을 정한 두 팀원이 가장 먼저 보는 실행 안내다. 현재 저장소에는 기획·데이터·모델 명세와
공통 API 계약이 있고 실행 가능한 애플리케이션은 아직 없다. 역할을 정한 뒤에도 바로 화면부터 만들지
않고, 두 흐름이 공유할 데이터의 의미를 먼저 검증한다.

## 1. 확정된 역할과 남은 교차 책임

기획자·사용자 담당은 확정됐다. [`TEAM_WORKFLOW.md`](TEAM_WORKFLOW.md)의 역할 배정표에서 남은 두 교차
책임을 정한다.

| 결정 | 담당·선택 방법 |
| --- | --- |
| 기획자 서비스 담당 | 홍성주 |
| 사용자 서비스 담당 | 박지성 |
| 공유 데이터·예측 계약 관리자 | TBD — Python 데이터 작업과 공통 schema 변경을 주도할 사람 |
| 통합 검토자 | TBD — 계약 관리자가 아닌 팀원. 상대 PR과 전체 demo를 검토 |

두 역할의 작업량은 완전히 같지 않다. 기획자 담당은 form·예측·LLM 연결이 크고, 사용자 담당은
캘린더·지도·상태 동기화와 반응형 UI가 크다. 데이터·모델 작업은 별도 세 번째 역할이 아니라 두 사람의
교차 책임이며, 계약 관리자가 구현을 주도하고 상대가 의미와 화면 영향을 검토한다.

## 2. 둘이 함께 먼저 끝낼 데이터 게이트

첫 기능 branch를 만들기 전에 다음 결과를 공동으로 확인한다.

1. 각자 `.env.example`을 `.env`로 복사하고 필요한 API key를 로컬에만 저장한다.
2. TourAPI `searchFestival2`의 실제 응답에서 행사 ID, 이름, 기간, 지역 코드와 좌표를 확인한다.
3. 같은 지역·기간의 관광 데이터랩 지역 방문자 값을 확보한다.
4. 두 자료의 결합률, 결측률, 시간·공간 단위와 label의 의미를 기록한다.
5. 축제별 수요라고 방어할 수 있는지 go/no-go를 결정한다.

축제별 label을 설명할 수 없으면 특정 축제 관람객 수를 주장하지 않는다. 이 경우 이미 정한 대안대로
지역·기간별 관광 혼잡 또는 방문수요 상대지수로 전환한다. 자세한 절차는
[`DATA_AND_APIS.md`](DATA_AND_APIS.md)를 따른다.

## 3. 데이터 게이트와 동시에 검증할 공통 계약 v0.1

실제 API가 준비되는 동안 두 화면은 구현 시작용 v0.1 기준선인 [`SHARED_SPEC.md`](SHARED_SPEC.md)와
[`../contracts/openapi.yaml`](../contracts/openapi.yaml)의 같은 mock contract를 사용한다. 계약 관리자가
실제 TourAPI mapping에서 차이가 발견되면 변경안을 만들고 통합 검토자가 확인한다.

| 계약 | 반드시 포함할 내용 |
| --- | --- |
| `Event` | `event_id`, source, source ID, 이름, 유형, 시작·종료, 지역 코드, 주소, 좌표, 대표 이미지 |
| `Venue` | `venue_id`, 이름, 주소, 좌표, 수용 규모, 접근성과 주변 시설 |
| `Prediction` | 종류, 단위, 기준시각, `p10·p50·p90` 또는 score, 신뢰도, 출처, version, 한계 |
| `SearchFilter` | 검색어, 날짜 범위, 지역, 행사 유형, 정렬 |
| `ApiError` | 안정적인 오류 코드, 사용자 메시지, 재시도 가능 여부, fallback |

실제 데이터 mapping을 검증하는 동안 양쪽 담당자는 기준선과 다른 필드명이나 수요 표현을 화면에 굳히지
않는다. 지역 방문수요, 특정 행사 관람객, 혼잡 등급과 티켓 수요 등급은 같은 뜻이 아니므로 별도 필드와
문구로 다룬다.

## 4. 역할별 첫 번째 작업 묶음

### 기획자 서비스 담당

첫 목표는 LLM 없이도 끝까지 동작하는 작은 기획 흐름이다.

1. 대형 지역축제 기획자와 소규모 독립 기획자·가수 scenario를 하나씩 쓴다.
2. [`PLANNER_WORKFLOW.md`](PLANNER_WORKFLOW.md)의 입력을 `MVP 필수`, `선택`, `추후`, `제외`로 나눈다.
3. 핵심 질문 10~15개, 입력 검증과 결과 화면의 wireflow를 만든다.
4. 합의한 `Event`·`Prediction` mock으로 규칙 기반 진단 결과를 연결한다.
5. 정상, 누락, 모순, 외부 API 실패와 예측 실패 상태를 확인한다.

첫 PR의 권장 범위는 대표 scenario, MVP 입력표, wireflow와 mock request·response다. LightGBM이나 LLM
연결은 이 PR의 완료 조건이 아니다.

### 사용자 서비스 담당

첫 목표는 mock 행사로 캘린더·지도·상세 탐색 흐름을 확정하는 것이다.

1. 역할 배정이 끝났으므로 EVENT-US 공개 캘린더와 지도를 조사하고 확인한 사실과 추론을 나눠 기록한다.
2. desktop·mobile page flow, filter, URL 상태, 로딩·빈 결과·오류 상태를 정리한다.
3. 합의한 `Event`·`SearchFilter` mock으로 목록·캘린더·지도·상세 wireflow를 만든다.
4. 캘린더 날짜, 검색·지역 filter와 지도 marker 선택이 같은 상태를 사용하도록 설계한다.
5. TourAPI 필드와 흥할지도 예측 필드를 화면에서 어떻게 구분할지 정한다.

첫 PR의 권장 범위는 벤치마킹 기록, page inventory, wireflow와 mock event 목록이다. EVENT-US의 상호,
문구, 이미지, 아이콘, source code를 복사하지 않고 공개 동작을 자체 기술로 구현한다. 상세 작업 기준은
[`VISITOR_WORKFLOW.md`](VISITOR_WORKFLOW.md)를 따른다.

## 5. 초기 PR 순서

| 순서 | branch 예시 | 담당 | 결과 |
| ---: | --- | --- | --- |
| 1 | `chore/shared-data-gate` | 계약 관리자 작성, 상대 검토 | API 응답·label go/no-go, contract v0.1 mapping 확인 |
| 2 | `docs/planner-mvp-flow` | 기획자 담당 | 대표 scenario, MVP 입력과 입력→결과 wireflow |
| 2 | `docs/visitor-mvp-flow` | 사용자 담당 | 벤치마킹, page inventory와 캘린더→지도→상세 wireflow |
| 3 | `chore/shared-scaffold` | 두 명 공동 | Next.js·FastAPI 골격, mock contract와 검증 명령 |
| 4 | `feat/planner-mvp-flow` | 기획자 담당 | mock 기반 입력→규칙 진단 흐름 |
| 4 | `feat/visitor-mvp-flow` | 사용자 담당 | mock 기반 목록→캘린더·지도→상세 흐름 |
| 5 | `chore/shared-tourapi` | 계약 관리자 작성, 상대 검토 | 실제 TourAPI adapter와 공통 오류·출처 처리 |

같은 순서 번호의 두 PR은 공통 contract 확인 후 병렬로 진행할 수 있다. application은 기록된 결정대로 Next.js·FastAPI로
scaffolding한다. 공통 파일을 동시에 바꾸지 말고 계약 변경이 필요하면 먼저 작은 shared PR로 분리한다.

## 6. 파일 소유권 원칙

실제 폴더는 기술 스택을 정하고 scaffolding할 때 만든다. 그 전까지는 다음 경계로 충돌을 피한다.

| 영역 | 주 작성자 | 필수 검토자 |
| --- | --- | --- |
| `docs/PLANNER_WORKFLOW.md`, 향후 planner 화면·route | 기획자 담당 | 사용자 담당 |
| `docs/VISITOR_WORKFLOW.md`, 향후 visitor 화면·route | 사용자 담당 | 기획자 담당 |
| 수집·정제·지역 코드·공통 schema·prediction API | 계약 관리자 | 통합 검토자 |
| model 학습·평가·version | 계약 관리자 주도 | 두 명 공동 승인 |
| `README.md`, 서비스 명세, 결정 로그, 배포 설정 | 변경을 제안한 사람 | 상대 담당 |

소유권은 상대 파일을 수정할 수 없다는 뜻이 아니라, 동시에 쓰지 않고 주 담당자가 최종 일관성을 책임진다는
뜻이다.

## 7. 각 작업의 완료 정의

기능 PR은 다음 항목을 만족해야 한다.

- 담당 persona의 정상 흐름이 시작부터 결과까지 이어진다.
- 로딩, 빈 결과, 잘못된 입력과 외부 API 실패가 처리된다.
- mock과 실제 API가 같은 공통 contract를 사용한다.
- 수치의 종류, 단위, 기준시각, 출처와 한계가 보인다.
- TourAPI가 실제로 사용되는 화면과 필드를 설명할 수 있다.
- desktop·mobile 핵심 상태를 확인한다.
- 실행·검증 방법과 실제 확인 결과를 문서에 남긴다.
- 상대 담당자가 PR과 사용자 흐름을 검토한다.
- 해당 작업이 강화하는 1차·최종 심사 항목을 적는다.

## 8. 주간 운영

- 시작할 때 이번 주의 각자 한 가지 end-to-end 목표와 공유 contract 변경 여부를 적는다.
- 중간에 공통 schema가 필요하면 메신저 합의로 끝내지 않고 작은 PR로 기록한다.
- 주 1회 기획자 흐름과 사용자 흐름을 같은 행사·같은 prediction ID로 이어서 시연한다.
- 완료되지 않은 기능 수보다 실제로 재현되는 사용자 흐름, 오류 처리와 데이터 근거를 우선한다.
- 범위를 줄여야 하면 LLM, SHAP, 학습 모델 순으로 미루고 TourAPI 기반 최소 흐름은 유지한다.

## 9. 문서 읽는 순서

1. [`SERVICE_SPEC.md`](SERVICE_SPEC.md): 누구의 어떤 문제를 푸는지
2. [`TEAM_WORKFLOW.md`](TEAM_WORKFLOW.md): 역할별 책임과 협업 규칙
3. [`SHARED_SPEC.md`](SHARED_SPEC.md): 함께 쓰는 field·API·오류 계약
4. 담당별 [`PLANNER_WORKFLOW.md`](PLANNER_WORKFLOW.md) 또는 [`VISITOR_WORKFLOW.md`](VISITOR_WORKFLOW.md)
5. [`DATA_AND_APIS.md`](DATA_AND_APIS.md): 첫 데이터 게이트
6. [`MODEL_PLAN.md`](MODEL_PLAN.md): 공통 예측 입력·출력과 검증
7. [`DELIVERY_MILESTONES.md`](DELIVERY_MILESTONES.md): 단계별 구현 경계
8. [`EVALUATION_CRITERIA.md`](EVALUATION_CRITERIA.md): 심사기준 점검
9. [`DECISION_LOG.md`](DECISION_LOG.md): 확정 사항과 미결 사항
