# HeungMap project guidance

HeungMap (흥할지도) predicts regional visitor demand (visitor-days per sigungu, p10·p50·p90) for the
dates of a festival and serves the same prediction to planners and visitors. 2026 Tourism Data Contest
award winner (designated task 9). Live: https://heungmap.vercel.app (Next.js on Vercel, FastAPI in Docker
Compose on a self-hosted ARM64 VM behind a Caddy reverse proxy; a systemd timer retrains the model daily).

## Read first

`README.md`, `docs/MODEL_CARD.md`, `docs/DEPLOY_RUNBOOK.md`, `contracts/openapi.yaml`, `docs/DECISION_LOG.md`.

## Invariants

- Korea Tourism Organization TourAPI usage must stay visible in the product and the docs.
- Never present regional visitors or modeled ranges as actual festival attendance.
- Keep API keys, `.env`, raw/processed data, model artifacts, virtual environments and build output out of Git.
- `contracts/openapi.yaml` is the single HTTP contract; `backend/tests/test_openapi_contract.py` checks it.
- Record material product, data and architecture decisions in `docs/DECISION_LOG.md`.
- Public docs carry no personal names, server addresses or account identifiers; use placeholders such as `<서버>`.

## Verify

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests -q
cd frontend && npm run typecheck && npm run lint && npm run build
```
