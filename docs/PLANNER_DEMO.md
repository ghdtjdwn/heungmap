# 기획자 기능 3분 시연

## 준비

1. `.env`의 `LLM_PROVIDER=anthropic`, `LLM_MODEL`(발표용 `claude-fable-5-1`), `LLM_API_KEY`를 확인하고 FastAPI, Next.js를
   실행합니다. 모델을 바꾼 뒤에는 `PYTHONPATH=backend .venv/bin/python backend/scripts/evaluate_llm.py --output
   data/processed/llm-eval-<모델>.json`으로 5개 시나리오를 다시 확인합니다.
2. `PYTHONPATH=backend .venv/bin/python backend/scripts/verify_daily_model.py`가 `"status": "ready"`인지,
   `last_predictable_target_date`가 시연 행사일 이후인지 확인합니다. 실행 중에는
   `curl http://127.0.0.1:8000/api/v1/system/model-status`로도 볼 수 있습니다. 샘플 행사 일정은 **오늘부터 30일 이내
   시작**이어야 하고, 신뢰도 `높음`이 나오도록 홀드아웃 오차가 작은 시군구(예: 해운대구 3.4%·제주시 1.6%·수원시 2.7%, 2026-09-18 v5 기준)로 고릅니다.
3. <http://localhost:3000>에서 모의 로그인 후 기획자 역할을 선택합니다. 브라우저 저장소에 민감정보가 없는지 확인합니다.
4. 예시 일정은 오늘 기준으로 자동 계산되고 지역은 해운대구·마포구로 정해져 있어 항상 실제 모델 예측이 나옵니다(D35).
   `대형 행사 샘플`과 `소규모 독립 행사 샘플`을 각각 한 번 분석해 응답 지연과 fallback 상태를 확인합니다.

2026-09-18 `claude-sonnet-5`(effort medium) 평가의 5개 scenario는 21–36초, 실제 예시 입력은 49–109초였습니다(D36).
발표용 `claude-fable-5-1`은 더 오래 걸릴 수 있으므로 시연 전에 같은 평가로 다시 측정하고 약 1분의 대기 여유를 둡니다. 장비 상태에 따라 달라질 수 있으며 서버 성능 수치로 일반화하지 않습니다.

## 3분 순서

| 시간 | 화면과 설명 |
| --- | --- |
| 0:00–0:30 | 기획 목록에서 대형 샘플을 열고 단계형 입력, 자동 저장, TourAPI 장소 검색과 Kakao 주소·좌표 선택을 보여줍니다. 수용인원은 공식 근거가 없어 빈 값으로 남길 수 있음을 말합니다. |
| 0:30–1:10 | 분석을 실행해 `데이터 분석 중 → 로컬 AI 보고서 작성 중 → 결과 검증 중` 상태를 보여줍니다. 지도에서 행사장과 TourAPI 주변 관광정보 목록의 동기화를 보여줍니다. |
| 1:10–1:45 | 먼저 **흥행 진단** 카드(방문 시기·지난 회차 규모·같은 기간 축제·신뢰도)로 과제 9번 질문에 답하고, 수요 진단의 **행사기간 시군구 방문자-일 p10~p90 범위**, 지역별 신뢰도, 평소 대비 지역 방문수요 수준, TreeSHAP 요인을 보여줍니다. `근거·출처` 탭에서 `실제값`(문체부 보고 전년 방문객 — 같은 이름 축제가 있을 때), `파생값`(계절 기준선·이 시군구 홀드아웃 오차), `가정`과 출처를 따라갑니다. 방문자-일은 축제 관람객 수가 아니라고 말합니다. |
| 1:45–2:15 | 대안 비교와 What-if를 열어 규모·예산·장소 조건 변화가 규칙 결과에 미치는 영향을 보여줍니다. LLM은 계산값을 바꾸지 않고 근거를 실행 문장으로 정리합니다. |
| 2:15–2:40 | 소규모 독립 샘플 결과로 이동해 대형 행사와 다른 예산·장소 검증 우선순위를 확인합니다. |
| 2:40–3:00 | Markdown·JSON 저장과 PDF 인쇄 진입, 분석 version 이력을 보여준 뒤 모의 로그인 상태와 실제 Google 연결·배포 제외, 초안의 기기 한계를 밝힙니다. |

## 예상 질문

| 질문 | 답변 |
| --- | --- |
| 예측한 관람객 수인가요? | 아닙니다. 행사기간 동안 그 시군구 전체를 찾는 방문자-일(날짜별 방문자 합)의 예측 범위입니다. 같은 사람이 이틀 오면 2로 셉니다. 축제 관람객은 주최 측이 문체부에 낸 전년 실적이 있을 때 "실제값"으로 따로 보여줍니다. |
| 얼마나 정확한가요? | 행사 30일 전 시점 정보만으로 2026-08-01~19 시험 구간(4,446 지역·일)에서 WAPE 3.94%, 기준선 대비 7.5% 개선입니다. 학습에 전혀 쓰지 않은 08-16~19 전향 평가에서도 WAPE 4.43%(기준선 4.98%)였습니다. 작은 관광 군 지역은 오차가 7~8%로 커서 신뢰도를 지역별로 따로 표시합니다. "정확도 N%"로 말하지 않습니다. |
| 축제 정보는 왜 모델 입력에 없나요? | TourAPI 축제 일정을 입력으로 넣어 같은 조건에서 비교했지만 개선이 0.05% 수준이고 축제 진행일에도 나아지지 않아 채택하지 않았습니다. 시군구 전체 방문수요는 계절·성장 기준선으로 대부분 설명되고, 개별 축제 효과는 이 단위에서 드러나지 않습니다. |
| 한국관광공사 데이터는 어디에 쓰나요? | `searchFestival2` 데이터 게이트, `searchKeyword2` 장소 후보, `locationBasedList2` 주변 관광정보에 사용하며 각 결과에 source와 조회시각을 보존합니다. |
| AI가 숫자나 근거를 만들 수 있나요? | 서버가 입력에 없는 숫자, 알 수 없는 evidence, 대안 수, 고정 제약과 사람 검토 표시를 검증하고 실패하면 규칙 보고서로 전환합니다. |
| 학습 모델과 SHAP은 무엇을 하나요? | 계절·성장 기준선이 기본 예측을 만들고 LightGBM이 그 오차를 최대 40%까지만 보정합니다. 요인은 LightGBM 내장 TreeSHAP 기여도입니다. 초기 축제 단위 모델(2026-09-06)은 기준선보다 나빠 버렸고, 지금 모델은 사전에 정한 5개 채택 조건을 통과한 것만 씁니다. |
| 모델이 오래되면요? | 방문자 자료는 약 30일 늦게 공개됩니다. 자료 기준일 60일이 지나면 숫자를 만들지 않고 `예측 불가`를 표시합니다. `refresh_daily_forecast.py` 한 번으로 새 자료를 받아 재학습하고, 채택 조건을 통과한 경우에만 서비스가 새 모델로 바뀝니다. |
| 지도나 LLM이 실패하면요? | 검색 목록·수동 입력·분석 snapshot을 보존하고 지도는 목록으로, LLM은 규칙 보고서로 전환합니다. |
| 초안은 다른 컴퓨터에서도 보이나요? | 초안은 계정별 현재 브라우저 localStorage에만 남습니다. 계정·세션·분석·공개 행사는 서버 SQLite에 저장하지만 초안 동기화는 제공하지 않습니다. |

## 통합 시연 추가 순서

분석 결과에서 공개 정보·별도 소개문을 확인하고 동의 후 공개합니다. 역할을 사용자로 전환해
목록·달력·지도에서 공개 행사를 찾고 상세에서 기획 분석과 같은 prediction ID·모델 버전·방문자-일 범위를 확인합니다. 기획자로 돌아와
공개를 철회하고 사용자 탐색에서 사라지는지 확인합니다. 내부 예산·메모·보고서는 공개하지 않습니다.

## Windows 재현 체크리스트

Windows에서는 아직 실제 실행하지 않았습니다. PowerShell에서 다음 순서로 재현하고 결과를 공동 확인합니다.

```powershell
py -m venv .venv
.\.venv\Scripts\python -m pip install -r backend\requirements-dev.txt
.\.venv\Scripts\python -m pip install -r backend\requirements-model.txt
$env:PYTHONPATH="backend"
.\.venv\Scripts\python -m pytest backend\tests -q
.\.venv\Scripts\python backend\scripts\verify_daily_model.py
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
(`npx playwright install chrome`: 현재 테스트는 Chrome 채널 사용), 한글 표시, 다운로드와 인쇄 진입,
모바일 viewport입니다. 기본 E2E는 별도 3100·8100 포트와 테스트 SQLite를 사용합니다.
