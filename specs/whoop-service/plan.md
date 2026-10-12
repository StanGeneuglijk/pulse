# Plan: whoop-service

**Spec:** `spec.md` · **Constitution:** [`../constitution.md`](../constitution.md)

## Summary

An async FastAPI API and one or more RQ worker processes, sharing Postgres and Redis. The API handles OAuth and reads, and turns "sync" into queued jobs; workers run one user's sync per job. Scaling is two independent levers: the number of worker processes (users synced at once) and a per-job semaphore (requests to WHOOP at once per user). `core/` holds everything product-agnostic so later services reuse its shape.

## Technical context

| | |
|---|---|
| Language / framework | Python 3.12, FastAPI, async SQLAlchemy 2 + asyncpg, httpx |
| Queue | Redis + RQ (jobs enqueued by dotted path + plain args) |
| Storage | Postgres (Supabase in production), Alembic migrations |
| Security | Fernet for tokens at rest, OAuth2 + PKCE, per-user `read_token` |
| Testing | pytest + respx (WHOOP mocked), real Postgres/Redis containers |
| Tooling | uv, ruff, mypy, Docker multi-stage build |
| Deploy target | Render web service (API) + background worker |

## Constitution check

| Principle | How this plan satisfies it |
|---|---|
| 1–4 Layering | `core/` has no WHOOP imports; `client.py` is the only WHOOP HTTP caller; `api/main.py` only aggregates; `workers/run.py` only boots |
| 5 Async I/O | asyncpg, `httpx.AsyncClient`, `redis.asyncio` throughout |
| 6 Explicit `user_id` | every function takes it; nothing ambient |
| 7 Upserts | `ON CONFLICT (user_id, whoop_record_id)` with a content-hash `WHERE` |
| 8 Job args | `enqueue("services.whoop.sync.sync_one_user", user_id, ...)` |
| 9–11 Failure | domain exceptions mapped only in `api/main.py`; typed parsing at the WHOOP boundary; retry 429/5xx only |
| 12–16 Config/secrets | `Settings` + `WhoopSettings`; distinct secrets; tokens encrypted |
| 17–18 Auth | OAuth authenticates the account; `API_KEY` / `read_token` authenticate the caller |
| 19–20 Logging | structlog JSON; `user_id`/`job_id` bound per unit of work, cleared in `finally` |

Deviations: none.

## Project structure

```
whoop-service/
├── api/main.py              # include routers, map DomainError -> HTTP, /health
├── workers/run.py           # boot an RQ worker on the sync queue
├── core/                    # product-agnostic
│   ├── config.py db.py redis_client.py queue.py logging.py clock.py
│   ├── auth.py crypto.py exceptions.py health.py locks.py
│   └── oauth_state.py one_time_code.py request_logging.py log_models.py
├── services/whoop/
│   ├── router.py            # OAuth, reads, sync triggers
│   ├── sync.py              # one user's unit of work
│   ├── client.py            # WHOOP HTTP: exchange, refresh, profile, paginated fetch
│   ├── circuit_breaker.py   # shared fast-fail when WHOOP is down
│   ├── crud.py models.py schemas.py whoop_types.py
│   └── auth.py config.py exceptions.py activity_log.py
├── alembic/
└── tests/
```

## Key decisions

| Decision | Chosen | Rejected, and why |
|---|---|---|
| Scaling unit | One job per user on a queue, N worker processes | One process looping over users — throughput capped by one loop |
| Worker concurrency | Processes (RQ) + a per-job semaphore | Unbounded `gather` — WHOOP rate limits |
| Idempotency | Upsert on (user, WHOOP id) + content hash | Delete-and-insert — non-atomic, rewrites unchanged rows |
| Identity across services | A per-user `read_token` issued here | A separate auth service — no second identity need yet |
| Handing the token to a browser | Single-use code, redeemed server-side | Token in the redirect URL — ends up in history and logs |
| Returning users | Match on WHOOP's account id | New row per login — duplicates with dead refresh tokens |
| DB pooling | `NullPool`; Supabase's pooler pools | App-side pool — conflicts with transaction-mode pooling |
| Request logs | Structured stdout | A row per request — mostly health-check noise |

## Data model (outline)

- `users` — id, `whoop_user_id` (unique), encrypted access/refresh token, expiry, connected flag, `read_token` (unique).
- `recoveries`, `sleeps`, `workouts` — user_id → users, `whoop_record_id`, score, `recorded_at`, `content_hash`; unique (user_id, whoop_record_id).
- `sync_job_logs`, `user_activity_logs`, `error_logs` — append-only; `user_id` without a foreign key so a failure for an unknown user still logs.

## API surface (outline)

| Route | Auth | Purpose |
|---|---|---|
| `GET /auth/login` → `GET /auth/callback` | — | OAuth with state + PKCE; ends with a redirect carrying a one-time code |
| `POST /auth/exchange` | — (the code is the credential) | One-time code → `userId`, `readToken` |
| `GET /users/{id}/recovery` · `sleep` · `workout` | user | Records, `ETag`-aware |
| `GET /users/{id}/syncs` · `activity` | user | Recent attempts / hits |
| `POST /users/{id}/sync` | user | Queue one sync (debounced) |
| `POST /sync/batch` | operator | Queue one sync per connected user (debounced, capped) |
| `GET /health` | — | Postgres + Redis reachable |

## Hosting

API and worker are two Render services from one Docker image, in the same region as the Supabase database; Redis on Upstash. A GitHub Actions schedule calls `/sync/batch`. See `docs/hosting.md`.

**Redis command budget.** Upstash's free plan allows 500K commands a month (about 16K a day), so nothing may poll Redis in a loop. The worker runs **without RQ's scheduler**: its one-second loop used about 345K commands a day and took the sync down in October 2026. Sync-job retries are therefore immediate (`Retry(max=…)` with no interval), and backoff against WHOOP lives in the client's per-request retry.

The other steady Redis user is the host's health check: Render calls `/health` every ~10 s on each API, and a fresh connection plus `PING` cost 4 commands, about 100K a day across the three APIs, which would empty a fresh database in under a week. So `/health` reuses a successful Redis ping for `REDIS_HEALTH_TTL_SECONDS` (5 minutes; a failure is never reused), and `core/redis_client.py` connects with `driver_info=None` to skip the two `CLIENT SETINFO` calls. That brings the health checks to about 2K commands a day across all three. Measure with the Upstash MCP server's statistics after any change that adds Redis calls to a polled path.

## What would change this design

- WHOOP webhooks become reliable → sync on event, keep the batch as a safety net.
- One worker can't keep up with the batch → raise `numInstances`; nothing else changes.
- A second product needs the same identity → move `read_token` issuance into its own small service.
