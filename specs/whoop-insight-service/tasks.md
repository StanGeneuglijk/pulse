# Tasks: whoop-insight-service

`[P]` = can run in parallel with the tasks next to it · `[USn]` = the user story a task serves.
Every task ends with `uv run ruff check .`, `uv run mypy .` and `uv run pytest` green.

## Phase 1 — Setup

- [x] T001 Skeleton: `pyproject.toml`, `api/`, `core/`, `services/insight/`, `tests/`, `Dockerfile`, `docker-compose.yml` (own Postgres/Redis ports).
- [x] T002 Copy `core/` from whoop-service; drop crypto, OAuth state, queue.

**Checkpoint:** `/health` green locally.

## Phase 2 — Foundation (blocks every story)

- [x] T003 Alembic with `version_table="insight_alembic_version"`; migration for `insights`, `insight_job_logs`, `insight_activity_logs`.
- [x] T004 [P] `whoop_read.py` — read-only recoveries/sleeps/workouts window on a private `MetaData`.
- [x] T005 [P] `llm.py` — `LLMClient` protocol, `LLMResult`; `tests/` fake client injected via `dependency_overrides`.
- [x] T006 [P] `auth.py` — operator key or the user's `read_token` from whoop-service's `users`.
- [x] T007 `config.py` + `pricing.py` — model setting validated against the price table.

**Checkpoint:** a migration against a database that already has whoop-service's tables creates only this service's tables.

## Phase 3 — US1 Get an insight (P1, MVP)

- [x] T008 [US1] `config.PERIOD_POLICY` — window, effort, max output tokens per period.
- [x] T009 [US1] `prompt.py` — system prompt framed by period; dated, scaled data lines.
- [x] T010 [US1] `providers/anthropic_client.py` — one Messages call; SDK errors → `LLMProviderError`; cached factory with timeout.
- [x] T011 [US1] `generate.py` — read window → empty check → prompt → LLM → upsert → job log.
- [x] T012 [US1] `crud.upsert_insight` + `content_hash`; `POST /insights/generate/{id}`.
- [x] T013 [US1] Tests: happy path, empty window `422` with no LLM call, provider failure `502`.

**Checkpoint:** US1 scenarios pass with the fake client; `scripts/run_insight_example.py` produces a real insight.

## Phase 4 — US3 Never pay twice, never overspend (P1)

- [x] T014 [US3] `lock.py` — per-user `SET NX` + TTL longer than timeout × retries.
- [x] T015 [US3] `crud.total_spend_usd` — tokens summed per model in SQL × prices.
- [x] T016 [US3] Caps in `generate.py`: per-user, then platform, before the lock.
- [x] T017 [US3] Tests: locked `409`, per-user cap, platform cap, unchanged inputs, unpriced model fails at startup.

**Checkpoint:** US3 scenarios pass.

## Phase 5 — US2 Nutrition context (P2)

- [x] T018 [US2] `nutrition_read.py` — meals window and active goal, read-only.
- [x] T019 [US2] Prompt and content hash include nutrition when present; omitted when empty.
- [x] T020 [US2] Tests: with and without nutrition data.

**Checkpoint:** US2 scenarios pass.

## Phase 6 — US4 History and usage (P3)

- [x] T021 [US4] List, latest, usage and activity routes; operator-only `/spend`.
- [x] T022 [US4] Tests: filtering, ordering, another user's data `401`.

## Phase 7 — Polish and ship

- [x] T023 `render.yaml`; RLS on every table; migrations applied to the shared database.
- [x] T024 README and `LEARNINGS.md`.

**Checkpoint:** deployed; a real user generates a real insight from the UI.
