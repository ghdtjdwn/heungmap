# 로컬 데이터 경로

현재 운영 학습·추론 경로는 `backend/app/demand/forecasting.py`와 `daily_service.py`입니다.
원본 파일 목록은 `backend/app/demand/training_inputs.py`가 정하고 `visitors-*-refresh-*.jsonl` 갱신 파일을 자동으로 포함합니다.
문체부 축제별 방문객 후보는 `backend/app/attendance`에서 별도 감사합니다. 재현 명령과 평가 분할은
[모델 실행·평가](../docs/MODEL_EVALUATION.md)를 따릅니다. 채택 모델은
`processed/daily-forecast-production-v*/`(가장 큰 번호의 채택 폴더), 미채택 축제별 후보는 `processed/attendance-model-release/`에
저장되며 모두 Git에서 제외합니다.

`raw/`와 `processed/`의 실제 내용은 Git에서 제외합니다. schema, synthetic fixture와 실행 코드는
`backend/app/data_gate`와 `backend/tests/fixtures/data_gate`에 있습니다.

```bash
PYTHONPATH=backend .venv/bin/python -m app.data_gate.cli collect festivals \
  --start 20250101 --end 20251231 --rows 1000 --max-pages 5 \
  --output data/raw/festivals-2025.jsonl

PYTHONPATH=backend .venv/bin/python -m app.data_gate.cli collect festivals \
  --start 20260101 --end 20260831 --rows 1000 --max-pages 5 \
  --output data/raw/festivals-2026-jan-aug.jsonl

PYTHONPATH=backend .venv/bin/python -m app.data_gate.cli collect visitors \
  --start 20250101 --end 20251231 --rows 10000 --max-pages 40 \
  --output data/raw/visitors-2025-full.jsonl

PYTHONPATH=backend .venv/bin/python -m app.data_gate.cli collect visitors \
  --start 20260101 --end 20260831 --rows 10000 --max-pages 25 \
  --output data/raw/visitors-2026-jan-aug.jsonl

PYTHONPATH=backend .venv/bin/python -m app.data_gate.cli build \
  --festivals data/raw/festivals-2025.jsonl data/raw/festivals-2026-jan-aug.jsonl \
  --visitors-jsonl data/raw/visitors-2025-full.jsonl data/raw/visitors-2026-jan-aug.jsonl

.venv/bin/pip install -r backend/requirements-model.txt
PYTHONPATH=backend .venv/bin/python backend/scripts/train_daily_forecast.py \
  --output-dir data/processed/daily-forecast-reproduction

# 새 방문자 자료 append 수집 + 다음 production-v* 재학습 (분할일 자동)
PYTHONPATH=backend .venv/bin/python backend/scripts/refresh_daily_forecast.py
PYTHONPATH=backend .venv/bin/python backend/scripts/verify_daily_model.py

# 문체부 전년 보고 방문객 조회표 (실제값 근거 표시용)
PYTHONPATH=backend .venv/bin/python backend/scripts/build_mcst_lookup.py

PYTHONPATH=backend .venv/bin/python backend/scripts/collect_mcst_festivals.py \
  --output-dir data/raw/mcst-festivals-new
```

한국관광 데이터랩에서 공식 CSV를 받은 경우 두 번째 수집 명령 대신
`--visitors-csv data/raw/visitors.csv`를 사용합니다. 수집은 완료 page 이후부터 재개하며 각 page에
조회시각과 원본 응답 item을 함께 보관합니다. `quality-report.json`의 `gate_passed`가 `true`일 때만
실제 학습 모델을 평가합니다. 데이터 게이트 통과와 제품 모델 채택은 별도 판정이며, 평가 script가
`model_adopted=false`를 반환하면 규칙 mock을 유지하고 SHAP을 계산하지 않습니다.
