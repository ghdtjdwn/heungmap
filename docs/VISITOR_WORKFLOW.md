# 사용자 서비스 작업 계획

## 목표와 현재 범위

사용자가 날짜·지역·관심사를 기준으로 실제 축제를 찾고, 캘린더와 지도에서 같은 검색 상태를 유지하며,
상세 화면에서 예상 혼잡·티켓 수요와 주변 주차·숙박·관광 정보를 확인하게 한다.

현재 MVP의 기준 데이터는 TourAPI로 확인 가능한 축제·지역 행사다. 콘서트와 클럽 공연은 별도 행사·수요
데이터를 확보한 뒤 확장한다. 이 문서는 역할을 맡은 사람이 바로 조사와 설계를 시작하기 위한 후보 목록이며,
구현 완료를 뜻하지 않는다.

## 담당 범위

사용자 서비스 담당자는 다음 흐름을 end-to-end로 책임진다.

- 공개 EVENT-US 캘린더·지도 벤치마킹과 증거 기록
- 행사 검색, filter, 목록, 캘린더, 지도와 상세 화면
- URL query와 화면 상태 동기화
- TourAPI 행사·주변 정보 adapter 연결
- 공통 prediction 결과의 혼잡·티켓 수요 표현
- Kakao Map marker, viewport, 선택 행사와 목록 동기화
- desktop·mobile·keyboard 접근성
- 로딩, 빈 결과, 위치 권한 거부, 지도·API 실패와 fallback
- 사용자 흐름 test와 상대 담당자 review 반영

행사·장소·prediction·오류 공통 계약은 단독으로 바꾸지 않는다. 변경이 필요하면 계약 관리자와 기획자
서비스 담당의 화면 영향을 함께 검토한다.

## EVENT-US 조사 순서

역할이 정해진 뒤 공개 화면을 직접 확인해 다음 결과를 남긴다.

1. 캘린더·지도·행사 상세 진입 경로와 page inventory
2. desktop·mobile screenshot 또는 관찰 기록과 확인 날짜
3. 검색, 날짜, 지역, 카테고리, 정렬 filter의 동작
4. 날짜 선택, 지도 이동·확대, marker·목록 선택의 상태 변화
5. 새로고침·뒤로 가기·공유 URL에서 유지되는 query 상태
6. 로딩, 빈 결과, 오류와 위치 권한 거부 상태
7. 확인한 사실, 구현을 위한 추론과 흥할지도에서 변경할 부분

공개 동작과 정보구조만 참고한다. 제3자의 source code, 상호, logo, 문구, image와 icon을 복사하지 않고
흥할지도 component와 데이터로 독립 구현한다.

## 목표 사용자 흐름

```text
행사 탐색 진입
  → 검색·날짜·지역·유형 filter
  → 목록·캘린더·지도 중 보기 선택
  → 날짜 또는 marker로 행사 선택
  → 행사 상세
  → 혼잡·티켓 수요와 근거 확인
  → 주차·숙박·주변 관광 확인
  → filter로 돌아가거나 공유
```

목록, 캘린더와 지도는 별개 검색을 만들지 않고 하나의 `SearchFilter` 상태와 같은 행사 결과를 사용한다.

## 화면별 후보 기능

### 탐색·목록

- 행사명·지역 통합 검색
- 오늘, 이번 주말, 이번 달과 직접 날짜 범위
- 광역·기초지자체, 거리 반경과 현재 지도 영역
- 축제·공연·전시·체험 등 행사 유형
- 무료·유료, 실내·실외, 가족·무장애 등 검증된 filter
- 최신순, 시작일순, 거리순과 수요·혼잡순 후보
- list card의 행사명, 기간, 장소, 이미지, 유형, 출처와 수요 요약
- filter 초기화, 적용 개수와 검색 결과 수

### 행사 캘린더

- 월 이동, 오늘 이동과 선택 날짜 표시
- 날짜별 행사 수와 대표 행사 표시
- 여러 날 진행되는 행사의 시작·진행·종료 구분
- 날짜 선택 시 목록·지도 결과 동기화
- 월 경계, 기간 행사와 시간대 처리
- mobile에서 일정 목록으로 전환 가능한 구조

### 행사 지도

- Kakao Map marker와 marker cluster 후보
- 현재 지도 영역에서 재검색
- marker 선택과 list card 강조 동기화
- 선택 행사에 맞춘 상세 preview
- 동일 좌표·밀집 marker 처리
- 사용자 위치는 권한 허용 시에만 사용
- 위치 권한 거부, 지도 SDK 실패와 좌표 없는 행사 fallback

### 행사 상세

- 행사명, 이미지, 유형, 기간, 운영시간, 주소와 공식 링크
- TourAPI 출처, 원본 갱신 시각과 제공 정보
- 예상 혼잡도·티켓 수요 등급, 기준시각, 신뢰도와 한계
- 실제 관람객과 지역 방문수요를 구분하는 문구
- 주변 주차·숙박·음식점·관광지와 거리
- 무장애·반려동물 등 확인된 상세 정보
- 날씨·교통·방문 주의사항 후보
- 캘린더·지도 복귀와 현재 검색 조건 유지
- URL 공유와 존재하지 않거나 종료된 행사 상태

## 상태와 URL 원칙

다음 값은 가능한 한 URL query에 보존해 새로고침·뒤로 가기·공유가 가능하게 한다.

```text
view
query
start_date
end_date
region_code
event_type
sort
map_bounds
selected_event_id
```

지도 확대 수준처럼 URL이 지나치게 자주 바뀌는 값은 debounce하거나 명시적인 `이 지역 검색` 동작 뒤에만
반영한다. URL, client state와 server 요청의 우선순위를 기술 스택 확정 시 기록한다.

## 필요한 공통 데이터

### 행사 card·calendar·marker

```text
event_id
source
source_event_id
title
event_type
start_at
end_at
region_code
address
latitude
longitude
thumbnail_url
price_summary
prediction_summary
updated_at
```

### 사용자용 prediction 요약

```text
prediction_id
prediction_type
as_of
target_period
congestion_level
ticket_demand_level
p10
p50
p90
unit
confidence
source_refs
limitations
fallback_used
```

필드 이름과 의미는 [`MODEL_PLAN.md`](MODEL_PLAN.md)의 공통 prediction 계약을 따르며, 값이 없는 경우를
정상 상태로 지원한다.

## 필수 UI 상태

| 상태 | 사용자에게 보여줄 것 |
| --- | --- |
| 첫 진입 | 기본 날짜 범위와 탐색 방법 |
| 로딩 | 어떤 결과를 불러오는지와 skeleton |
| 결과 없음 | 적용 filter, 초기화와 날짜·지역 변경 방법 |
| 일부 데이터 없음 | 행사는 표시하되 없는 이미지·좌표·prediction을 구분 |
| TourAPI 실패 | cached/mock이 아닌 실제 상태, 재시도와 가능한 fallback |
| 지도 실패 | 목록·캘린더를 계속 사용할 수 있는 대체 화면 |
| 위치 권한 거부 | 수동 지역 선택 방법 |
| prediction 실패 | 행사 정보는 유지하고 예측을 사용할 수 없다고 표시 |
| 잘못된 URL | 유효한 filter로 복구하거나 명확한 안내 |

## 구현 단계

### 단계 0 — 조사와 mock 흐름

- EVENT-US 공개 화면 조사 기록
- page inventory와 desktop·mobile wireflow
- `Event`, `SearchFilter`, `Prediction` mock contract
- 목록·캘린더·지도·상세의 최소 탐색 흐름

### 단계 1 — 실제 TourAPI와 지도

- `searchFestival2` 목록과 상세 연결
- 지역·날짜·유형 filter
- Kakao Map marker와 목록 동기화
- 주변 관광·숙박 등 검증된 정보
- API·지도 오류 fallback

### 단계 2 — 예측 결과 연결

- 공통 prediction API 연결
- 혼잡·티켓 수요, 신뢰도·기준시각·한계 표시
- 기획자 서비스와 같은 행사·prediction ID 사용
- 값 변경과 fallback 상태 확인

### 단계 3 — 사용성 개선

- 반응형·keyboard·screen reader 점검
- URL 공유·뒤로 가기·상태 복원
- 성능, marker 밀집과 이미지 최적화
- 접근성·다국어·관광 코스 확장 후보

## 첫 작업 체크리스트

- [x] 사용자 서비스 담당자 이름 확정 — 박지성
- [ ] EVENT-US 조사 날짜·범위와 결과 기록 위치 확정
- [ ] 공개 캘린더·지도·상세 page flow 조사
- [ ] 확인한 사실과 구현 추론 분리
- [ ] 핵심 persona와 대표 탐색 scenario 작성
- [ ] MVP 화면·filter와 추후 항목 구분
- [ ] desktop·mobile wireflow 작성
- [ ] 공통 `Event`·`SearchFilter`·`Prediction` contract 검토
- [ ] mock 행사 목록으로 캘린더·지도·상세 흐름 연결
- [ ] 필수 UI 상태 구현·확인
- [ ] 실제 TourAPI와 Kakao Map 연결
- [ ] 상대 담당자와 같은 행사·prediction 결과 통합 확인

## 완료 조건

- 같은 검색·날짜·지역 filter가 목록, 캘린더와 지도에 일관되게 적용된다.
- 사용자가 캘린더 또는 지도에서 행사를 골라 상세와 주변 정보를 확인할 수 있다.
- 새로고침, 뒤로 가기와 공유 URL에서 필요한 탐색 상태가 유지된다.
- TourAPI 정보와 흥할지도 자체 예측이 출처·기준시각과 함께 구분된다.
- 위치 권한이나 지도·prediction이 실패해도 행사 탐색을 계속할 수 있다.
- desktop·mobile과 keyboard 핵심 흐름을 실제로 확인한다.
- EVENT-US 비교표에 구현·변경·미구현 상태가 정직하게 기록된다.

## 미결 사항

- frontend를 Next.js와 Streamlit 중 무엇으로 구현할지
- 캘린더·지도 layout과 interaction의 실제 벤치마킹 결과
- MVP filter와 정렬 범위
- 현재 위치·거리순 기능 포함 여부
- 주변 시설에 사용할 TourAPI 세부 endpoint
- 사용자용 티켓 수요 지표의 데이터와 경계값
- 행사 즐겨찾기·알림·로그인 포함 여부
