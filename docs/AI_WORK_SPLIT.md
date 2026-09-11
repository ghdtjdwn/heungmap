# AI 작업 분담과 병렬 진행 안내

## 목적

기획자 서비스의 AI를 두 사람이 같은 방식으로 중복 구현하지 않고, **수요를 계산하는 모델**과
**계산 결과를 설명하는 LLM**으로 나눠 병렬 진행한다. 두 작업은 같은 `Prediction`과 Planning Context를
사용하지만 책임, 검증 방법과 실행 환경이 다르다.

```text
TourAPI·지역 방문자 데이터
  → 수요 모델·baseline 비교
  → 공통 Prediction
  → 기획자 규칙 진단
  → LLM 기획 설명
```

LLM은 수요 모델의 숫자를 새로 만들거나 변경하지 않는다. 수요 모델이 채택 기준을 통과하지 못하면
제품은 기존 규칙 기반 mock 상대지수를 유지하고, LLM은 그 한계를 포함해 설명한다.

## 현재 출발점

- 데이터 게이트: 514건·76.37% 결합으로 통과
- 학습 모델: 2025–2026 시간 분할에서 LightGBM MAE가 지역 중앙값 baseline보다 16.23% 나빠 NO-GO
- 제품 수요값: `relative_demand_score`, `is_mock=true`, `confidence=low` 유지
- 기획 설명: Ollama `qwen3.5:9b` adapter와 규칙 fallback이 구현되어 있고 5개 대표 scenario로 검증됨
- 공통 계약: `docs/SHARED_SPEC.md`와 `contracts/openapi.yaml`을 그대로 사용

따라서 이번 작업은 기존 LightGBM을 바로 제품에 연결하는 단계가 아니다. 데이터와 feature를 개선해
채택 가능성을 다시 평가하는 실험과, 이미 계산된 결과를 더 안전하고 유용하게 설명하는 LLM 개선을
분리한다.

## 담당자와 환경

| 담당 | 기존 사용자 흐름 | 이번 AI 책임 | 주 실행 환경 | branch |
| --- | --- | --- | --- | --- |
| 박지성 | 방문객 서비스 | 데이터·수요 모델 실험, 공통 prediction 변경안 작성 | Windows, Intel i5-1240P, RAM 16GB | `feat/model-v2-experiment` |
| 홍성주 | 기획자 서비스 | 기획자 LLM 추천·보고서 품질, model-before-LLM 흐름 유지 | 16GB Apple Silicon MacBook | `feat/planner-llm-improvement` |

현재 Windows 장비는 표 형태의 514건 데이터와 LightGBM 실험에 충분하며 GPU가 필요하지 않다. Ollama는
설치되어 있지 않고 내장 GPU를 사용하므로 로컬 9B LLM 반복 평가는 이미 실행 기록이 있는 MacBook에서
담당한다. 역할은 운영체제가 아니라 작업 성격을 기준으로 정하며, 한쪽이 막히면 재현 명령으로 교차
확인한다.

## 박지성 — 수요 모델 실험

### 목표

새 데이터나 검증된 feature가 시간 일반화 성능을 개선하는지 확인한다. 모델 종류를 늘리는 것보다
label·가용성·누수와 baseline 비교를 먼저 검증한다.

### 작업 범위

1. 기존 데이터 게이트와 `backend/scripts/evaluate_demand_model.py` 결과를 재현한다.
2. `MODEL_PLAN.md` 후보 중 예측 시점에 확보 가능한 feature만 작은 단위로 추가한다.
3. 각 feature의 출처, 결측률, 누수 위험과 사용자 가치를 기록한다.
4. 같은 지역·시기 중앙값 baseline과 LightGBM을 동일한 분할로 비교한다.
5. 과거→미래 시간 분할과 미관측 지역 group 검증 결과를 모두 기록한다.
6. 성능이 채택 기준을 통과하기 전에는 model artifact나 실제 추론을 제품 endpoint에 연결하지 않는다.

### 결과물

- 재현 가능한 feature 생성·평가 코드
- baseline과 후보 모델의 MAE·Median AE·RMSE 비교표
- 지역·기간·label별 오류 분석
- 채택 또는 보류 판정과 근거
- 필요할 때만 공통 `Prediction` 계약 변경안

SHAP은 모델이 채택된 뒤에만 계산한다. 지역 방문수요 증가율을 실제 축제 관람객 수나 티켓 수요로
표현하지 않는다.

## 홍성주 — 기획자 LLM 개선

### 목표

공통 Prediction과 Planning Context를 근거로 기획자가 실행할 수 있는 설명을 만들되, 새로운 사실이나
예측 숫자를 생성하지 않게 한다.

### 작업 범위

1. Ollama `qwen3.5:9b`의 현재 5개 대표 scenario 평가를 재현한다.
2. 대형 기획자와 소규모 독립 기획자의 설명·우선순위 차이를 개선한다.
3. 출력 JSON schema, 요청한 대안 개수와 `evidence_ref`를 검증한다.
4. 입력에 없는 숫자, 확정적 성과 표현과 모델 한계 누락을 실패로 처리한다.
5. timeout·미설정·잘못된 출력에서 기존 규칙 보고서로 돌아가는지 확인한다.
6. 수요 모델의 값과 `model_version`을 읽기만 하고 변경하지 않는다.

### 결과물

- prompt·provider adapter의 작은 개선
- 대표·경계 scenario별 평가 기록
- 생성 방식, 근거와 사람 확인 필요 여부가 보이는 기획 보고서
- LLM 실패 시 규칙 fallback 회귀 테스트

LLM 응답 품질 개선은 수요 모델 채택과 독립적으로 검증할 수 있다. 다만 mock Prediction을 읽었다면
생성 문장에서도 실제 예측이 아니라는 한계를 유지한다.

## 함께 먼저 고정할 경계

두 branch를 만들기 전에 다음 기준을 확인한다.

- 기준 commit은 같은 최신 `main`이다.
- `contracts/openapi.yaml`과 `docs/SHARED_SPEC.md`의 `Prediction` 의미를 임의로 바꾸지 않는다.
- 공통 파일 변경이 필요하면 먼저 별도 shared PR로 분리하거나 상대 담당자의 검토 순서를 정한다.
- API key, `.env`, raw·processed dataset, model artifact, 가상환경과 LLM 출력 원본은 commit하지 않는다.
- 실험 결과와 생성 문장은 같은 행사·prediction ID를 사용한다.

동시 수정을 피해야 할 공통 파일은 다음과 같다.

```text
contracts/openapi.yaml
backend/app/schemas.py
backend/app/main.py
backend/app/services/planner.py
docs/SHARED_SPEC.md
docs/MODEL_PLAN.md
docs/DECISION_LOG.md
```

공통 파일이 필요하지 않은 실험 코드, 평가 script와 LLM scenario는 각 branch에서 독립적으로 진행할 수
있다.

## 시작 명령

### Windows — 수요 모델

```powershell
git switch main
git pull --ff-only
git switch -c feat/model-v2-experiment
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-model.txt
$env:PYTHONPATH="backend"
.\.venv\Scripts\python.exe backend\scripts\evaluate_demand_model.py
```

### macOS — 기획자 LLM

```bash
git switch main
git pull --ff-only
git switch -c feat/planner-llm-improvement
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements-dev.txt
ollama pull qwen3.5:9b
PYTHONPATH=backend .venv/bin/python backend/scripts/evaluate_llm.py \
  --output data/processed/llm-eval.json
```

두 환경 모두 작업 전 전체 테스트를 한 번 실행해 기준 상태를 남긴다. Windows의 테스트에서는 로컬
`.env`에 Kakao key가 있으면 주변 장소 테스트에 실제 결과가 개입할 수 있으므로, 결정론적 전체 테스트는
`KAKAO_REST_API_KEY`를 비운 process 환경에서 실행한다.

## PR과 통합 순서

1. 이 역할 분담 문서를 먼저 병합한다.
2. 두 담당자가 최신 `main`에서 각 branch를 만든다.
3. 수요 모델 PR은 실험·평가 결과를 제출하되 채택 전 제품 연결을 포함하지 않는다.
4. LLM PR은 기존 Prediction 계약 안에서 prompt·검증·fallback을 개선한다.
5. 공통 schema 변경은 별도 shared PR로 두 사람이 함께 검토한다.
6. 수요 모델이 baseline 대비 시간·group 검증 기준을 통과한 경우에만 별도 제품 연결 PR을 만든다.
7. 최종 통합에서는 같은 입력으로 수요 결과→규칙 진단→LLM 설명이 이어지고, 실패 fallback이 유지되는지
   두 사람이 함께 시연한다.

## 완료 판단

### 수요 모델

- 동일한 데이터·분할에서 baseline과 후보 모델을 재현할 수 있다.
- 시간 분할과 미관측 지역 검증을 모두 보고한다.
- 개선되지 않은 결과도 숨기지 않고 제품 미연결 상태를 유지한다.
- 값의 종류·단위·출처와 실제 관람객이 아니라는 한계를 설명한다.

### 기획자 LLM

- 구조화 출력과 evidence 참조 검증을 통과한다.
- 입력에 없는 숫자나 사실을 만들지 않는다.
- 대형·소규모 기획자 scenario에서 실행 가능한 우선순위를 제시한다.
- LLM 장애 시 입력·수요 결과·규칙 보고서가 유지된다.
