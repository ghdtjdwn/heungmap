# 기능설명서용 서비스 캡처 (2026-09-20)

1차 심사 기능설명서(PPT)에 넣은 실제 서비스 화면입니다. 모두 로컬에서 실제 백엔드·실제
한국관광공사 OpenAPI·실제 학습 모델(`regional-daily-1.0-ab975d661247`)·실제 Claude 보고서를
띄운 상태에서 Playwright로 촬영했습니다(1440×900, 2배 해상도). 목업이 아닙니다.

| 파일 | 화면 |
| --- | --- |
| 01-landing / 02-landing-flow | 소개 페이지 |
| 03-onboarding | 역할 선택 |
| 04-planner-dashboard | 기획자 대시보드 |
| 05~09-wizard-* | 기획 7단계 입력(장소 검색은 searchKeyword2 실호출) |
| 10~14-result-* | 분석 결과: 예측 범위, 흥행 진단, TreeSHAP 요인, 주변 관광정보(locationBasedList2) |
| 15-result-report* | Claude 기획 보고서 (full은 전체 페이지) |
| 16-result-whatif* | 조건 비교(What-if) — 일정 변경 시 +36,229 방문자-일 |
| 17-result-evidence* | 근거·출처(출처 기관·데이터셋·조회 시각) |
| 18-result-publish-form / 18b | 행사 공개 |
| 19~22-visitor-* | 방문객 목록·지도·달력 |
| 23~26-visitor-* | 방문객 축제 상세·수요 지표·주변 주차/숙박 |

재촬영이 필요하면 backend(:8000)와 frontend(:3000)를 띄운 뒤 Playwright로 같은 흐름을 다시
돌리면 됩니다. 접속은 반드시 `localhost:3000`으로 합니다 — `127.0.0.1`로 들어가면
`HEUNGMAP_PUBLIC_ORIGIN`과 origin이 달라 로그인이 403으로 막힙니다.
