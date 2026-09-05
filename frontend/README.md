# 기획자 frontend

Next.js App Router 기반 기획자 화면이다. `/planner`에서 로컬 초안을 관리하고 `/planner/new`에서 단계형
입력을 작성하며 `/planner/result`에서 mock 수요 결과, 규칙 추천, 대안 비교와 보고서를 확인한다.

상세 기획 입력은 공통 계약을 바꾸지 않는 `PlanningDetails`로 저장한다. 장소 단계는 TourAPI 장소명 검색과 Kakao 주소·좌표 검색을 제공하고, 장소를 비워두면 결과에서 필요한 규모·접근성·시설 확인 순서를 추천한다. 분석 결과와 합친 `Planning Context 1.0`을 실제 LLM 추천 endpoint에 한 번 전달하고, 실패하면 규칙 보고서로 자동 전환한다. 최근 20개 분석 version, 날짜·지역·규모·장소 수용인원·예산·공간 What-if와 Markdown·JSON·PDF 내보내기를 제공한다.

```bash
npm install
npm run dev
```

개발 서버는 일반 `/api/v1/*` 요청을 `http://127.0.0.1:8000`의 FastAPI로 전달한다. 로컬 LLM 보고서는
첫 생성이 30초를 넘을 수 있어 브라우저가 같은 FastAPI에 직접 요청하며, 다른 주소를 쓸 때만
`NEXT_PUBLIC_API_BASE_URL`을 지정한다. FastAPI CORS는 localhost frontend만 허용한다. 로그인 전 초안과
분석 결과는 브라우저 `localStorage`에만 저장된다.
