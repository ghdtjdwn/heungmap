# UI 디자인 가이드

## 방향

흥할지도는 일반적인 관리 도구보다 `축제를 발견하는 설렘`과 `데이터로 준비하는 신뢰`가 함께 보여야 합니다.
사용자가 만든 지도 핀·펼친 지도 로고를 기준으로 밝은 배경, 선명한 초록의 정보 계층과 노란 강조색을
사용합니다. 장식은 줄이고 지도 좌표·경로에서 가져온 그래픽 언어를 필요한 곳에만 반복합니다.

## 제품 원칙

- 첫 화면에서 기획자와 방문객 두 흐름, 한국관광공사 TourAPI 사용, 수요 지표의 범위를 바로 이해할 수 있게 합니다.
- 지역 방문수요·방문자-일을 특정 축제 관람객, 실제 혼잡도나 티켓 수요처럼 표현하지 않습니다.
- 장식보다 다음 행동, 현재 상태, 데이터 출처와 오류 복구를 먼저 보이게 합니다.
- desktop과 mobile에서 같은 정보 순서와 행동 이름을 유지합니다.
- 색만으로 상태를 구분하지 않고 문구·아이콘·형태를 함께 사용합니다.

## 시각 토큰

| 용도 | 기준 |
| --- | --- |
| 배경 | background gray `#F4F5F2`, white `#FFFFFF` |
| 본문 | text `#1F2D26`, muted `#607067` |
| 핵심 행동 | main green `#16A34A`, dark green `#12823B` |
| 보조·강조 | sub green `#A7E3B1`, point yellow `#FACC15` |
| 모서리 | control 10~12px, card 16~24px |
| 그림자 | 낮은 대비로 작은 깊이만 표현하고 정보 card를 과도하게 띄우지 않음 |

## 로고 자산

- 브랜드 원본은 `docs/assets/heungmap-brand-guide.png`로 보관합니다.
- 웹 화면에서는 투명 배경 가로형 `frontend/public/assets/heungmap-logo.png`를 사용합니다.
- 로고의 비율과 지정 색상을 임의로 바꾸거나 효과를 추가하지 않습니다.
- 가로형 로고는 화면에서 너비 128px 이상을 권장해 글자 가독성을 유지합니다.

## 구현 순서

1. 브랜드, token, button·card·상태 표현
2. 소개와 역할 선택
3. 기획자 dashboard·wizard·결과
4. 방문객 목록·달력·지도·상세
5. 실제 desktop·mobile 브라우저와 keyboard 회귀 확인

## 화면 완료 조건

- 360px부터 desktop까지 가로 스크롤 없이 핵심 흐름을 완료할 수 있습니다.
- heading 순서, landmark, label, focus 표시와 44px 이상 주요 터치 영역을 유지합니다.
- loading·empty·partial·error 상태에서도 사용자가 다음 행동을 알 수 있습니다.
- mock·실제 모델, TourAPI·Kakao·기획자 입력의 출처가 섞이지 않습니다.
- typecheck, lint, production build와 관련 Playwright 시나리오를 통과합니다.
