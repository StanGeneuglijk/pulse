# Tasks: whoop-service

`[P]` = can run in parallel with the tasks next to it · `[USn]` = the user story a task serves.
Every task ends with `uv run ruff check .`, `uv run mypy .` and `uv run pytest` green.

## Phase 1 — Setup

- [x] T001 Project skeleton: `pyproject.toml` (uv), `api/`, `core/`, `services/whoop/`, `workers/`, `tests/`; ruff + mypy config.
- [x] T002 [P] `docker-compose.yml` with Postgres and Redis for local dev and tests.
- [x] T003 [P] Multi-stage `Dockerfile` (uv builder → slim runtime, non-root user).

**Checkpoint:** `uv run pytest` runs (zero tests) and `docker compose up postgres redis` is healthy.

## Phase 2 — Foundation (blocks every story)

- [x] T004 `core/config.py` — `Settings` from the environment; `.env.example`.
- [x] T005 `core/db.py` — async engine, session factory, `get_db` dependency; Alembic wired to it.
- [x] T006 [P] `core/logging.py` — structlog JSON; `core/exceptions.py` — `DomainError` hierarchy.
- [x] T007 [P] `core/redis_client.py` and `core/queue.py` — async Redis per call; RQ connection and re-exports.
- [x] T008 `api/main.py` — app, one `DomainError` handler, `/health` checking Postgres and Redis.
- [x] T009 `core/auth.py` — `bearer_token()`, master-key check, `require_api_key`.

**Checkpoint:** `GET /health` returns `{"status":"ok"}`; a protected test route returns `401` without the key.

## Phase 3 — US1 Connect my WHOOP account (P1)

- [x] T010 [US1] `core/crypto.py` — Fernet encrypt/decrypt; `TOKEN_ENCRYPTION_KEY` validated at startup.
- [x] T011 [US1] `services/whoop/models.py` — `User` (WHOOP id, encrypted tokens, `read_token`); migration.
- [x] T012 [US1] `core/oauth_state.py` — Redis state + PKCE verifier, consumed once.
- [x] T013 [US1] `client.py` — code exchange, refresh, profile lookup; `UpstreamAuthError` on rejection.
- [x] T014 [US1] `GET /auth/login`, `GET /auth/callback` — state check, exchange, identify account, upsert user.
- [x] T015 [US1] `core/one_time_code.py` + `POST /auth/exchange` — single-use code → `read_token`.
- [x] T016 [US1] Tests: happy path, unknown state, reconnect reuses the user, code reuse rejected.

**Checkpoint:** US1 scenarios 1–4 pass against mocked WHOOP.

## Phase 4 — US2 My data stays in sync (P1)

- [x] T017 [US2] `whoop_types.py` — pydantic models for WHOOP records (the trust boundary).
- [x] T018 [US2] `Recovery`/`Sleep`/`Workout` models with (user, WHOOP id) unique constraints; migration.
- [x] T019 [US2] `crud.py` — upserts with content-hash `WHERE`; one commit per sync.
- [x] T020 [US2] `client.fetch_all` — three collections concurrently under a semaphore, `next_token` pagination, retry 429/5xx.
- [x] T021 [US2] `sync.py` — `sync_one_user`: valid token (refresh + re-store) → fetch since last sync → upsert → `SyncJobLog`; revoked grant → disconnect.
- [x] T022 [US2] Callback enqueues a first sync.
- [x] T023 [US2] Tests: idempotent re-sync, pagination, incremental fetch, refresh, revoked grant.

**Checkpoint:** US2 scenarios pass; running a sync twice leaves identical rows.

## Phase 5 — US3 Sync everyone on a schedule (P1)

- [x] T024 [US3] `workers/run.py` — worker on the sync queue.
- [x] T025 [US3] `POST /sync/batch` — `enqueue_many`, debounce lock, max-users cap, operator key only.
- [x] T026 [US3] `circuit_breaker.py` — Redis failure counter checked before each fetch.
- [x] T027 [US3] Worker integration tests: retries, a failing job never blocks healthy ones.

**Checkpoint:** a batch over many users queues one job each; a real worker drains them in tests.

## Phase 6 — US4 Read my own data (P2)

- [x] T028 [US4] `services/whoop/auth.py` — `require_user_access`: operator key or that user's `read_token`.
- [x] T029 [US4] Read routes with `ETag`/`304`; `/syncs`, `/activity`; activity logging.
- [x] T030 [US4] `POST /users/{id}/sync` with a per-user debounce.
- [x] T031 [US4] Tests: own data readable, another user's `401`, `304` on match, debounce.

**Checkpoint:** US4 scenarios pass.

## Phase 7 — Polish and ship

- [x] T032 `render.yaml` — API + worker, same region as the database.
- [x] T033 Repo-root CI: lint, types, tests, image scan; scheduled workflow calling `/sync/batch`.
- [x] T034 README and hosting guide.

**Checkpoint:** deployed; `/health` green; a real login syncs real data.
