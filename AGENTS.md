# HeungMap project guidance

## Read first

Read `README.md`, then `docs/SERVICE_SPEC.md`, `docs/TEAM_WORKFLOW.md`, `docs/DELIVERY_MILESTONES.md`, `docs/DATA_AND_APIS.md`, `docs/EVALUATION_CRITERIA.md`, `docs/DECISION_LOG.md`, `docs/OPENAPI_CATALOG.md`, and `docs/TECH_STACK.md`. Treat these repository documents as the persistent source of truth.

## Product and delivery invariants

- HeungMap is a two-person beginner project for the 2026 Tourism Data Contest designated task 9.
- Korea Tourism Organization OpenAPI usage is mandatory and must remain visible in the product and submission evidence.
- Prove the data gate before broad implementation: call `searchFestival2`, collect matching regional visitor data, and determine whether a defensible label can be joined.
- Complete the runnable baseline product before starting the learned model, SHAP explanation, or LLM report.
- Do not present regional visitors, modeled concentration, or relative indices as actual festival attendance.
- Keep API keys, `.env`, raw or processed datasets, model artifacts, virtual environments, caches, and build output out of Git.
- Preserve a reproducible path from source API response to derived features, prediction, and user-facing explanation.
- Record material product, data, and architecture decisions in `docs/DECISION_LOG.md`.
- Split the two-person team by planner and visitor user journeys as defined in `docs/TEAM_WORKFLOW.md`; keep shared data and prediction contracts jointly reviewed.
- Prefer small, tutorial-sized changes that can be run and verified by both team members on macOS and Windows.
