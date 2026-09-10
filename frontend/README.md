# 흥할지도 frontend

현재 통합 흐름은 소개 → 모의 로그인 → 역할 선택 → 기획자/사용자 서비스입니다.
인증 설정·공개 행사·Google 연결은 [통합 안내](../docs/SERVICE_INTEGRATION.md)를 따릅니다.

Next.js App Router 기반 기획자 화면이다. `/planner`에서 로컬 초안을 관리하고 `/planner/new`에서 단계형
입력을 작성하며 `/planner/result`에서 mock 수요 결과, 규칙 추천, 대안 비교와 보고서를 확인한다.

방문객 화면은 `/visitor?view=list`에서 TourAPI 축제를 20건씩 목록으로 탐색하고,
`/visitor?view=map`과 `/visitor?view=calendar`에서 같은 검색·날짜·지역 조건을 지도·달력으로 비교한다.
지도·달력은 페이지당 최대 100건이며 모든 보기에서 다음 페이지로 이동할 수 있다. 상태는
URL query로 공유되며 `/visitor/{eventId}` 상세로 이어진다. 기획자가 공개한 행사도 함께 탐색한다.

상세 기획 입력은 공통 계약을 바꾸지 않는 `PlanningDetails`로 저장한다. 장소 단계는 TourAPI 장소명 검색과 Kakao 주소·좌표 검색을 제공하고, 장소를 비워두면 결과에서 필요한 규모·접근성·시설 확인 순서를 추천한다. 분석 결과와 합친 `Planning Context 1.0`을 실제 LLM 추천 endpoint에 한 번 전달하고, 실패하면 규칙 보고서로 자동 전환한다. 최근 20개 분석 version, 날짜·지역·규모·장소 수용인원·예산·공간 What-if와 Markdown·JSON·PDF 내보내기를 제공한다.

```bash
npm install
npm run dev
```

개발 서버는 일반 `/api/v1/*` 요청을 `http://127.0.0.1:8000`의 FastAPI로 전달한다. 장시간 LLM 보고서는
전용 Next.js route를 통해 같은 origin에서 요청한다. 다른 backend 주소를 쓸 때는 frontend 프로세스에
`HEUNGMAP_BACKEND_URL`을 지정한다. 초안은 계정별 localStorage, 계정·역할·분석 snapshot·공개 행사는
로컬 서버 SQLite에 저장된다.

기본 `npm run e2e`는 3100·8100 포트에 독립 mock 서버를 실행한다. 테스트 브라우저는 Chrome 채널이므로
Chrome 설치가 필요하다. 3000번 개발 서버를 재사용할 때는 해당 backend의 development/mock 설정과
`HEUNGMAP_PUBLIC_ORIGIN=http://localhost:3000`, frontend 연결을 먼저 확인한다.
실제 로컬 API 테스트는 공개 행사를 쓰므로 운영 서버나 보존할 데이터가 있는 서버를 대상으로 실행하지 않는다.

```powershell
$env:HEUNGMAP_E2E_BASE_URL='http://localhost:3000'
npm run e2e -- e2e/visitor.spec.ts
```
