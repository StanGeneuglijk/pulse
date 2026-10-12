# Plan: whoop-insight-service

**Spec:** `spec.md` · **Constitution:** [`../constitution.md`](../constitution.md) · **LLM reasoning:** `whoop-insight-service/LEARNINGS.md`

## Summary

A single async FastAPI service. One request = one generation, run inline: check caps, take a per-user lock, read the data window straight from the shared database, build a prompt, call Claude through a provider interface, upsert the result, log the usage. `core/` is copied from whoop-service and trimmed (no crypto, OAuth or queue). No worker: a generation is bounded (timeout × retries ≈ 100s worst case).

## Technical context

| | |
|---|---|
| Language / framework | Python 3.12, FastAPI, async SQLAlchemy + asyncpg |
| LLM | Anthropic Messages API behind an `LLMClient` protocol |
| Storage | The shared Postgres; own tables `insights`, `insight_*`; own Alembic version table |
| Locking | Redis `SET NX` per user |
| Testing | pytest with a fake `LLMClient`; real Postgres/Redis |
| Deploy target | One Render web service |

## Constitution check

| Principle | How this plan satisfies it |
|---|---|
| 1, 3 Layering | `core/` product-agnostic; `api/main.py` only aggregates |
| 2 (adapted) One external boundary | `providers/anthropic_client.py` is the only module importing the SDK |
| 5 Async I/O | async DB, Redis, and SDK client |
| 6 Explicit `user_id` | every function takes it |
| 7 Idempotent writes | upsert on (user, period, start, end, prompt version) + content hash |
| 9 Fail fast | empty window, lock, caps and provider errors are domain exceptions mapped in one place |
| 12–14 Config/secrets | `Settings` + `InsightSettings`; own `API_KEY`, own Anthropic key |
| 18 Scoped auth | `read_token` per user; `/spend` operator-only |
| 23 Scope discipline | no queue/worker until generations need one |

Deviations: C-VIII (jobs) doesn't apply — nothing is queued.

## Project structure

```
whoop-insight-service/
├── api/main.py
├── core/                        # copied from whoop-service, trimmed
├── services/insight/
│   ├── router.py                # routes
│   ├── generate.py              # orchestration of one generation
│   ├── llm.py                   # LLMClient protocol + LLMResult
│   ├── providers/               # Anthropic client, cached factory
│   ├── prompt.py                # system + user prompt; no I/O
│   ├── config.py                # model, PERIOD_POLICY, caps, timeouts
│   ├── pricing.py               # $/MTok per model
│   ├── whoop_read.py            # read-only Tables over whoop-service's data
│   ├── nutrition_read.py        # read-only Tables over nutrition data
│   ├── auth.py lock.py crud.py models.py schemas.py exceptions.py activity_log.py
├── alembic/                     # version_table = insight_alembic_version
├── scripts/run_insight_example.py
└── tests/
```

## Key decisions

| Decision | Chosen | Rejected, and why |
|---|---|---|
| Getting WHOOP data | Read whoop-service's tables directly, read-only | An HTTP call to whoop-service — extra hop, same data, same database |
| Owning vs. reading | Narrow `Table`s on a private `MetaData` | Mapping them on `Base` — Alembic would try to manage them |
| Provider coupling | `LLMClient` protocol + one provider module | SDK calls in orchestration — untestable offline, vendor leaks everywhere |
| Cost control | Per-period policy + caps before the call + lock + idempotency key | Post-hoc budget alerts — money already spent |
| Execution | Inline in the request | Queue + worker — not needed for a bounded call (revisit, see below) |
| Shared code | Copy `core/` | Shared package — couples three independent deploys for ~250 lines |

## Data model (outline)

- `insights` — user_id, period type, window start/end, prompt version, model, content, content hash; unique on (user, period type, start, end, prompt version).
- `insight_job_logs` — user_id, status, period, model, input/output tokens, duration, error.
- `insight_activity_logs` — user_id, route, time.

## API surface (outline)

| Route | Auth | Purpose |
|---|---|---|
| `POST /insights/generate/{id}?period=` | user | Generate (or return unchanged) |
| `GET /insights/{id}?period=` · `/latest?period=` | user | History / latest |
| `GET /insights/{id}/usage` · `/activity` | user | Counts, spend, hits |
| `GET /insights/spend` | operator | Platform spend vs. cap |
| `GET /health` | — | Postgres + Redis |

## Hosting

One Render web service in the database's region, sharing Supabase and Upstash with whoop-service. RLS enabled (no policies) on every table.

## What would change this design

- Generations regularly exceed ~100s → move to a queue and worker, return a job id.
- Daily insights for every user on a schedule → use the provider's batch API.
- A long, stable system prompt (few-shot examples) → enable prompt caching.
- A second LLM provider → one new module in `providers/` and one branch in the factory.
