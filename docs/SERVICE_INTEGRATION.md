# 통합 로컬 서비스

## 전달 상태 (2026-09-10)

[PR #23](https://github.com/ghdtjdwn/heungmap/pull/23)은 `548584e`로 `main`에 병합됐습니다.
방문객 PR #17은 통합 코드에 수정 사항이 포함돼 별도 병합 없이 닫혔습니다. 배포는 하지 않았고,
원격 CI 체크 결과도 없으므로 아래 검증은 로컬 실행 결과입니다. 병합 전 전달 기록은
[다음 세션 인계](NEXT_SESSION_COMMAND.md)를 참조합니다.

## 사용 흐름

1. backend와 frontend를 실행하고 http://localhost:3000 을 엽니다.
2. 소개 페이지의 로그인 버튼을 누르면 개발용 체험 계정으로 로그인합니다.
3. 처음에는 기획자/사용자를 선택합니다. 다음 로그인은 마지막 역할로 바로 들어갑니다.
4. 헤더에서 역할 전환·로그아웃, 로고에서 소개 페이지 이동을 할 수 있습니다.
5. 기획자는 단계별 입력→분석→LLM 또는 규칙 보고서→What-if·내보내기를 사용합니다.
6. 분석 결과의 공개 영역에서 별도 소개문을 작성하고 공개 항목에 동의하면 사용자에게 행사가 보입니다.
7. 사용자는 TourAPI 행사와 공개 행사를 목록·지도·달력에서 검색하고 상세·주변 지도·수요 지표를 확인합니다.
8. 기획자는 재분석한 내용으로 공개 갱신하거나 대시보드/결과에서 공개를 철회합니다.

예산·내부 메모·기획 보고서는 공개하지 않습니다. 공개한 예측은 기획 분석과 같은 ID·점수를 유지하되
비공개 입력을 설명하는 영향 요인·근거는 공개하지 않습니다. 실제 축제 관람객 수나 검증된 AI 예측이 아닙니다.

## 실행

기존 .env는 수정하지 않습니다. 새 설정이 없으면 development/mock, localhost:3000으로 시작합니다.
Python 가상환경에서 backend/requirements-dev.txt를 설치합니다(Authlib 추가 포함).
backend는 PYTHONPATH=backend .venv/bin/uvicorn app.main:app --reload --port 8000,
frontend는 cd frontend 후 npm run dev로 실행합니다.
Windows는 .venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --port 8000을 사용할 수 있습니다.

frontend의 API 요청은 같은 origin을 사용합니다. 장시간 LLM 요청은 전용 Next.js route로 전달하며
브라우저에 backend 주소·provider secret을 노출하지 않습니다. backend 주소를 변경할 때는 frontend
프로세스에 HEUNGMAP_BACKEND_URL을 설정합니다.

## 인증과 저장

- 계정·역할·세션·분석·공개 행사는 data/heungmap.sqlite3에 저장됩니다. Git에는 포함하지 않습니다.
- 초안은 로그인 계정별 localStorage에 저장됩니다. 로그아웃은 초안을 삭제하지 않습니다.
- 로그인 도입 전 저장한 초안은 대시보드의 '로그인 전 초안 가져오기'로 복사합니다.
- 세션은 7일 후 만료되며 로그아웃 시 서버에서 폐기합니다. 모의 계정은 브라우저의 별도 HttpOnly
  체험 쿠키로 구분합니다. 쿠키 삭제 시 다른 체험 계정이 됩니다.
- 계정별 초안 구분은 공유 브라우저에 대한 강한 보안 저장소가 아닙니다. 기기 간 초안 동기화는 제공하지 않습니다.
- 공개 행사는 해당 로컬 서버를 사용하는 클라이언트끼리 공유됩니다. 인터넷 공개·배포는 하지 않았습니다.
- 기획 분석·추천은 로그인 필요, 조회용 행사 API는 공개입니다. 역할은 서비스 선호이며 관리자 권한이 아닙니다.

## 배포 때 Google 연결

HEUNGMAP_ENV=production, HEUNGMAP_AUTH_MODE=google, HEUNGMAP_PUBLIC_ORIGIN=https://서비스도메인,
GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET을 backend 환경에 설정하고 정확히 같은 origin의
/api/v1/auth/google/callback을 Google Console의 승인 redirect URI에 등록합니다.
mock 모드로 production 실행 시 시작을 거부합니다. secret은 frontend 환경에 넣지 않습니다.

Google 인증 요청·코드 교환·PKCE·일회용 state·nonce·ID token 서명/issuer/audience/만료 검증·계정 연결과
세션 발급 경로를 구현했습니다. Google access/refresh token은 저장하지 않습니다.
로그인 취소·만료·검증 실패는 소개 페이지로 돌아가 재시도를 안내합니다.
실제 Google 프로젝트의 동의 화면·등록 도메인·실계정 왕복은 연결 시 별도 검증해야 합니다.

근거: [Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect),
[Authlib JWT 검증](https://docs.authlib.org/en/v1.7.0/jose/jwt.html).

## 검증

현재 통합 코드에서 backend 62개, 전체 브라우저 테스트 19개, frontend typecheck·lint·production build
통과를 확인했습니다. Google 실계정 왕복, 실제 SDK 타일과 외부 LLM 재호출 성공을 의미하지 않습니다.

- backend/tests: 기존 API 계약·외부 오류와 신규 계정·세션·origin·역할·OAuth 실패·공개 소유권 검증.
- frontend/e2e: 기존 기획자·방문객 회귀, 실제 로컬 API의 로그인/역할 기억/공개 연결 검증.
- npm run e2e는 3100(frontend), 8100(backend)에 독립 서버를 시작하고 data/e2e.sqlite3을 사용합니다.
  외부 TourAPI/지도/LLM은 기존 기능 테스트에서 fixture로 검증하며 실제 provider 검증과 구분합니다.
- mock 세션은 production에서 사용할 수 없지만 development backend와 production frontend build를
  조합한 로컬 시연은 가능합니다.

학습 모델·SHAP·실제 Google 계정 연결·운영 배포는 완료 범위에 포함하지 않습니다. 문서의 광범위한
입력/feature 후보, 예매·결제·알림·즐겨찾기는 모두 구현 약속이 아닌 추후 후보입니다.
