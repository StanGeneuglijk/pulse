# Tasks: whoop-nutrition-service

`[P]` = can run in parallel with the tasks next to it · `[USn]` = the user story a task serves.
Every task ends with `uv run ruff check .`, `uv run mypy .` and `uv run pytest` green.

## Phase 1 — Setup

- [x] T001 Skeleton mirroring whoop-insight-service: `pyproject.toml`, `api/`, `core/` (copied), `services/nutrition/`, `tests/`, `Dockerfile`, `docker-compose.yml`.

**Checkpoint:** `/health` green locally.

## Phase 2 — Foundation (blocks every story)

- [x] T002 Alembic with `version_table="nutrition_alembic_version"`; migration for conversations, messages, logs, items, goals, job and activity logs.
- [x] T003 [P] `auth.py` — `require_user_access`; `require_conversation_owner` (resolve caller first, then ownership).
- [x] T004 [P] `llm.py` — `ChatLLMClient`, `ChatMessage`, `MealProposal`, the `propose_meal_breakdown` tool schema (strict).
- [x] T005 [P] `config.py` + `pricing.py` — models validated against price tables; caps; context limit; request bounds.
- [x] T006 Fake chat client in `tests/conftest.py` via `dependency_overrides`.

**Checkpoint:** migrations create only `nutrition_*` tables in a database that already has the other services' tables.

## Phase 3 — US1 Log a meal by describing it (P1, MVP)

- [x] T007 [US1] `prompt.py` — rules (ask when unsure; don't call the tool until you can estimate), today's date, active goal.
- [x] T008 [US1] `providers/anthropic_client.py` — one call with the tool; parse `tool_use` into `MealProposal`; normalize the timestamp to UTC; malformed input → `LLMProviderError`.
- [x] T009 [US1] `chat.py` — create/get conversation → store user message → bounded history → end DB transaction → LLM → store reply → stage proposal → job log.
- [x] T010 [US1] `POST /nutrition/chat/{id}`.
- [x] T011 [US1] Tests: proposal returned and nothing saved; clarifying question; timezone conversion; malformed tool input.

**Checkpoint:** US1 scenarios pass with the fake client; `scripts/run_chat_example.py` holds a real conversation.

## Phase 4 — US2 Confirm before save (P1)

- [x] T012 [US2] `crud.confirm_meal` (meal + items, one transaction) and `discard_pending_meal`; `409` when nothing is pending.
- [x] T013 [US2] Confirm/discard routes guarded by `require_conversation_owner`.
- [x] T014 [US2] Tests: confirm, discard, double confirm `409`, another user's conversation `401`.

**Checkpoint:** US2 scenarios pass.

## Phase 5 — US5 Bounded cost (P1)

- [x] T015 [US5] `lock.py` — per-conversation `SET NX`; TTL longer than timeout × retries.
- [x] T016 [US5] `crud.total_spend_usd` (tokens and audio seconds per model, in SQL) and `enforce_spend_cap`.
- [x] T017 [US5] Tests: per-user and platform caps `402`; locked conversation `409`.

## Phase 6 — US3 Speak instead of typing (P2)

- [x] T018 [US3] `transcription.py` protocol; `providers/openai_whisper_client.py` (`verbose_json` for duration; MIME base type → file extension).
- [x] T019 [US3] Factory raising `TranscriptionNotConfiguredError` when no key; `POST /nutrition/chat/{id}/audio` — cap, size limit, transcribe, log seconds, same turn, return transcript.
- [x] T020 [US3] Tests: transcript runs the same pipeline; `503` without a key; `413` over the limit; transcription cost counted.

**Checkpoint:** US3 scenarios pass.

## Phase 7 — US4 Goals and summaries (P2)

- [x] T021 [US4] `set_goal` (one active per user), `GET`/`PUT /nutrition/goals/{id}`.
- [x] T022 [US4] `summarize` + `GET /nutrition/meals/{id}/summary`; meals list with bounded `days`.
- [x] T023 [US4] Tests: goal replacement, summary against a goal.

## Phase 8 — Polish and ship

- [x] T024 Usage/activity/spend routes; `render.yaml`; RLS on every table; migrations applied.
- [x] T025 README and `LEARNINGS.md`; confirm whoop-insight-service's `nutrition_read.py` matches the columns.

**Checkpoint:** deployed; a meal logged by voice in the UI appears in the next insight.
