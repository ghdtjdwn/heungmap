# 기획자 기능 3분 시연

## 준비

1. Ollama와 `qwen3.5:9b`, FastAPI, Next.js를 실행합니다.
2. <http://localhost:3000/planner>를 열고 브라우저 저장소에 민감정보가 없는지 확인합니다.
3. `대형 행사 샘플`과 `소규모 독립 행사 샘플`을 각각 한 번 분석해 응답 지연과 fallback 상태를 확인합니다.

2026-09-06 실제 로컬 평가의 5개 scenario 응답 시간은 31.054–51.978초였으므로 시연에서는 약 1분의
대기 여유를 둡니다. 장비 상태에 따라 달라질 수 있으며 서버 성능 수치로 일반화하지 않습니다.

## 3분 순서

| 시간 | 화면과 설명 |
| --- | --- |
| 0:00–0:30 | 기획 목록에서 대형 샘플을 열고 단계형 입력, 자동 저장, TourAPI 장소 검색과 Kakao 주소·좌표 선택을 보여줍니다. 수용인원은 공식 근거가 없어 빈 값으로 남길 수 있음을 말합니다. |
| 0:30–1:10 | 분석을 실행해 `데이터 분석 중 → 로컬 AI 보고서 작성 중 → 결과 검증 중` 상태를 보여줍니다. 지도에서 행사장과 TourAPI 주변 관광정보 목록의 동기화를 보여줍니다. |
| 1:10–1:45 | 결과의 `사용자 입력`, `실제값`, `파생값`, `MODEL MOCK`, `가정` 표시와 출처를 따라갑니다. 상대 수요점수는 실제 관람객 수가 아니며 학습 모델은 baseline·일반화 검증 때문에 보류됐다고 설명합니다. |
| 1:45–2:15 | 대안 비교와 What-if를 열어 규모·예산·장소 조건 변화가 규칙 결과에 미치는 영향을 보여줍니다. LLM은 계산값을 바꾸지 않고 근거를 실행 문장으로 정리합니다. |
| 2:15–2:40 | 소규모 독립 샘플 결과로 이동해 대형 행사와 다른 예산·장소 검증 우선순위를 확인합니다. |
| 2:40–3:00 | Markdown·JSON 저장과 PDF 인쇄 진입, 분석 version 이력을 보여준 뒤 로그인·배포 제외와 `localStorage`의 기기 한계를 밝힙니다. |

## 예상 질문

| 질문 | 답변 |
| --- | --- |
| 예측한 관람객 수인가요? | 아닙니다. 현재 수치는 입력 완성도와 규칙에 따른 0–100 상대지수이고 `MODEL MOCK`입니다. 지역 방문자도 특정 축제 관람객이 아닙니다. |
| 한국관광공사 데이터는 어디에 쓰나요? | `searchFestival2` 데이터 게이트, `searchKeyword2` 장소 후보, `locationBasedList2` 주변 관광정보에 사용하며 각 결과에 source와 조회시각을 보존합니다. |
| AI가 숫자나 근거를 만들 수 있나요? | 서버가 입력에 없는 숫자, 알 수 없는 evidence, 대안 수, 고정 제약과 사람 검토 표시를 검증하고 실패하면 규칙 보고서로 전환합니다. |
| 왜 학습 모델과 SHAP이 없나요? | 2025–2026 축제·방문자 514건을 76.37%로 결합해 게이트는 통과했습니다. 하지만 LightGBM의 시간 MAE가 baseline보다 16.23% 나빠 채택하지 않았습니다. SHAP은 채택 모델에만 계산합니다. |
| 지도나 LLM이 실패하면요? | 검색 목록·수동 입력·분석 snapshot을 보존하고 지도는 목록으로, LLM은 규칙 보고서로 전환합니다. |
| 초안은 다른 컴퓨터에서도 보이나요? | 로그인과 서버 저장을 제외했으므로 현재 브라우저 `localStorage`에만 남습니다. |

## Windows 재현 체크리스트

Windows에서는 아직 실제 실행하지 않았습니다. PowerShell에서 다음 순서로 재현하고 결과를 공동 확인합니다.

```powershell
py -m venv .venv
.\.venv\Scripts\python -m pip install -r backend\requirements-dev.txt
.\.venv\Scripts\python -m pip install -r backend\requirements-model.txt
$env:PYTHONPATH="backend"
.\.venv\Scripts\python -m pytest backend\tests -q
.\.venv\Scripts\python backend\scripts\evaluate_demand_model.py
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

별도 PowerShell에서 실행합니다.

```powershell
cd frontend
npm ci
npm run typecheck
npm run lint
npm run build
npm run e2e
npm run dev
```

확인 항목은 Node·Python version, `.env` 비공개, localhost 포트 8000·3000, Chromium 설치
(`npx playwright install chromium`), 한글 표시, 다운로드와 인쇄 진입, 모바일 viewport입니다.
