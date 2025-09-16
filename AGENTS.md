# Repository Guidelines

## Project Structure & Module Organization
SoloPilot’s Python agents live in `src/` with domain folders like `src/agents/dev` for the repo-aware builder, `src/providers` for LLM adapters, and `src/common` for shared primitives. The React UI sits in `frontend/`, infrastructure code in `infrastructure/`, and long-form references in `docs/`. Tests live in `tests/`, and helper utilities in `scripts/`.

## Build, Test, and Development Commands
Run `make venv` once to create the virtualenv; use `make install` after dependency updates. `make plan-dev` runs the analyser → planner → dev-agent loop against `sample_input/`, while `make dev` reruns the latest dev pass. `make test` executes pytest, `make lint` runs ruff, black, and isort with repo defaults, and `make docker`/`make docker-down` manage services from `docker-compose.yml`.

## Coding Style & Naming Conventions
Python code follows black with a 100-character line cap, four-space indentation, and snake_case symbols; classes and Pydantic models stay in PascalCase. Keep module names short and descriptive (e.g., `email_intake_router.py`). Use ruff to catch lint issues before review. In `frontend/`, prefer TypeScript, camelCase for functions and hooks, and PascalCase for React components. Configuration samples belong in `config/` and should never hard-code credentials.

## Testing Guidelines
Add or extend tests in `tests/`, mirroring the source package path (e.g., `tests/agents/test_dev_agent.py`). Name new files `test_*.py` and mark scenario helpers with pytest fixtures. Validate changes locally with `pytest` or `make test`; when adding edge-case logic, include regression examples from `sample_input/` where possible. Keep AWS-dependent tests opt-in by guarding them behind environment flags or the existing Bedrock smoke tests.

## Commit & Pull Request Guidelines
Write commits in imperative mood with a concise summary (“Add PDF annotation feature to email intake process”), mirroring current history. Bundle related work, and note migrations or data jobs in the body. Pull requests should link tracking issues, describe validation (test runs, UI screenshots), and call out configuration updates. Before review, ensure `make lint` and `make test` pass, attach relevant artifacts from `output/`, and note follow-up tasks for downstream agents.

## Security & Configuration Tips
Store secrets in your local environment or managed secret vaults; `.env` is intentionally excluded from git. For any AWS CLI or deployment action, use the `root` profile and target `us-east-2` (set `AWS_PROFILE=root` and `AWS_REGION=us-east-2` or pass `--profile root --region us-east-2`). When touching provider code, confirm `scripts/check_bedrock.py` succeeds before promoting changes. Update vector indexes via `make index` after adding large documentation sets.
