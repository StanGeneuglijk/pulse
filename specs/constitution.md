# Constitution

The non-negotiable principles every service in this repo is built and reviewed against.
Every plan (`plan.md`'s Constitution Check), code review and release checks against this
file and cites principles by ID (C-I, C-II, ...). If code and this file disagree, that's a
bug in one of them: fix it, don't let them coexist. The **Quality Gates** table says which
step checks which principle.

<!-- IDs are stable. plan.md, review findings and tasks.md cite principles by ID,
     so rewording a principle is fine but renumbering breaks those references.
     A new principle gets the next free ID. -->

## Core Principles

### Layering

#### C-I. `core/` has zero product-specific imports
No WHOOP field names, no `httpx` calls to WHOOP's API, no `services.whoop` imports.
`core/` is what a second product (nutrition, AI insight) would import unchanged.

#### C-II. `services/whoop/client.py` is the sole module that makes an HTTP request to WHOOP
Data fetch and OAuth token exchange/refresh alike. One narrow, necessary exception:
`services/whoop/router.py`'s `login()` route constructs a browser redirect to WHOOP's
authorization page, which means naming that URL: a redirect target the browser
follows, never a request this service makes itself.

#### C-III. `api/main.py` only aggregates
Router includes and exception-handler registration. No business logic, and no route
definitions of its own beyond `/health` and `/version` (which commit is deployed,
read from `Settings`).

#### C-IV. `workers/run.py` only boots
Import the modules RQ needs to resolve dotted job paths, construct a `Worker`, call
`.work()`. No business logic.

### Concurrency and data

#### C-V. No blocking I/O inside `async def`
Async SQLAlchemy + `asyncpg`, `httpx.AsyncClient`, throughout. A sync call inside an
async route stalls the whole event loop, not just one request.

#### C-VI. `user_id` is an explicit parameter everywhere
No ambient "current user", no thread-local. This is what makes the same code safe
across N concurrent worker processes.

#### C-VII. Every write is an upsert, keyed on `(user_id, whoop_record_id)`. Never a plain insert
`ON CONFLICT DO UPDATE`, with a `content_hash`-gated `WHERE` clause so an unchanged
re-sync is a genuine no-op write, not just a harmless overwrite.

#### C-VIII. Jobs are enqueued by dotted import path + plain serializable args
Never a function object or a live ORM object: the API process and worker processes
share no memory.

### Failure handling

#### C-IX. Fail fast, loud, and clear
Every layer raises the clearest `core/exceptions.py` domain exception the instant
something is wrong: never a silent `None`, a bare `ValueError`, or a swallowed
failure. Only `api/main.py`'s registered `@app.exception_handler`s decide what a
domain fact becomes as HTTP (status code + structured log line + response body). No
inline `HTTPException` in a route.

#### C-X. WHOOP's responses are parsed into typed models at the trust boundary
`services/whoop/whoop_types.py`, validated inside `client.py`. A WHOOP field rename
fails loudly there as a `pydantic.ValidationError`, never silently downstream as a
`None`.

#### C-XI. Retries distinguish retryable from non-retryable
429/5xx back off and retry; 401/403 (and any WHOOP auth rejection) raise immediately.
Retrying a bad credential just wastes time before the identical outcome.

### Config and secrets

#### C-XII. Every env var is read through a pydantic-settings `Settings` object
`core/config.py`'s `Settings` for product-agnostic infrastructure (database, cache,
caller auth, encryption key, deploy metadata), each product's own `<Product>Settings`
(`services/whoop/config.py`'s `WhoopSettings` here) for that product's own variables.
No bare `os.environ` reads anywhere in the codebase.

#### C-XIII. Every fixed, non-secret constant lives in its owning module's `config.py`
`core/`'s for product-agnostic infrastructure, each product's own
(`services/whoop/config.py` here) for that product's URLs, retry policy, and job/lock
TTLs, as a plain UPPER_CASE module attribute, never redefined or scattered elsewhere.
One file per product answers "what does this product depend on".

#### C-XIV. Distinct secrets protect distinct blast radii, never merged
`WHOOP_CLIENT_SECRET` / `TOKEN_ENCRYPTION_KEY` / `DATABASE_URL` / `API_KEY`: a leak of
one must not hand an attacker a second capability for free.

#### C-XV. A value's *format*, not just its presence, is validated at startup where it matters
`TOKEN_ENCRYPTION_KEY` is checked against `Fernet`'s own format at `Settings()`
construction: a malformed value fails at import, not deep inside a live OAuth callback.

#### C-XVI. Tokens are encrypted before every write, decrypted only at the point of use
`core/crypto.py`'s `Fernet` wrapper. No plaintext WHOOP token ever reaches the database.

### Authentication and authorization

#### C-XVII. Two authentication axes, never conflated
WHOOP OAuth (`services/whoop/whoop_oauth`) authenticates the WHOOP account being
*synced*; caller authentication (`core/auth.py` + `services/whoop/auth.py`)
authenticates *who's allowed to call this API*. Neither substitutes for the other.

#### C-XVIII. Caller authentication is scoped to what a route actually needs
The operator-level `API_KEY` (`core/auth.py`) guards routes with no single owning
`user_id` (`sync_batch`, which fans out to every connected user); a per-user
`read_token` (`services/whoop/auth.py`, `services/whoop/models.py`) guards routes
scoped to one `user_id`. Holding a valid key never implies access to every user's data.

### Observability

#### C-XIX. Structured JSON logging from line one, in every process
`configure_logging()` called once at process start, never inside a request handler or
job. Every log line is the same JSON shape regardless of which process produced it.

#### C-XX. `user_id` and `job_id` bound via `structlog.contextvars` for one unit of work, cleared in a `finally`
A worker process is long-running: skip the clear and a later job's logs can carry the
previous job's identifiers.

### API surface

#### C-XXI. Responses are camelCase JSON; Python stays snake_case throughout
`services/whoop/schemas.py`'s `alias_generator=to_camel` is the only place that
boundary is crossed. No camelCase Python identifiers anywhere in the codebase.

#### C-XXII. `/health` proves its dependencies are reachable, not just that the process is alive
Pings Postgres and Redis; raises `DependencyUnavailableError` (→ `503`) naming
whichever failed. A deploy platform routing on this check needs a truthful answer.
Postgres is checked on every call. A successful Redis ping may be reused for
`REDIS_HEALTH_TTL_SECONDS` (`core/config.py`, 5 minutes), because the host polls
`/health` every ~10 s and every Redis command counts against Upstash's quota; a failed
ping is never reused, so recovery and new failures still show within that window.

### Scope discipline

#### C-XXIII. Build the multi-tenant shape; don't build load-driven infrastructure without evidence it's needed
Queue/worker/`user_id`-scoped schema: yes, cheap now, expensive to retrofit.
Kubernetes, autoscaling, multi-region, per-tenant fairness: no. Retrofittable later
without a rewrite, and there is no second real user today to justify them.

## Quality Gates

One row per principle: which step of the assembly line checks it, and how. "Blocks"
means the step must not pass while the principle is violated. A principle with no
row here is a principle nobody checks.

| Principle | Checked at | How it is checked | Blocks? |
|-----------|------------|-------------------|---------|
| C-I core has no product imports | `/autoplan` eng phase, `/review` | no `services.*` import or WHOOP field name under any `core/` | Yes |
| C-II one WHOOP HTTP client | `/review` | no `httpx` request to a WHOOP URL outside `services/whoop/client.py` | Yes |
| C-III `api/main.py` only aggregates | `/review` | diff to `api/main.py` adds only router includes, handlers, `/health`, `/version` | Yes |
| C-IV `workers/run.py` only boots | `/review` | diff to `workers/run.py` adds no logic | Yes |
| C-V no blocking I/O in async | `/autoplan` eng phase, `/review` | no `requests`, sync DB driver or `time.sleep` inside `async def` without `run_in_threadpool` | Yes |
| C-VI explicit `user_id` | `/review` | no globals, thread-locals or context lookups for the current user | Yes |
| C-VII upserts only | `/review`, `/qa` | data writes use `ON CONFLICT DO UPDATE` on `(user_id, whoop_record_id)`; re-running a sync leaves row counts unchanged | Yes |
| C-VIII jobs by dotted path | `/review` | `enqueue(...)` takes a string path and plain args | Yes |
| C-IX fail fast via domain exceptions | `/review` | no inline `HTTPException`, no swallowed `except` | Yes |
| C-X typed trust boundary | `/review` | new WHOOP fields parsed in `whoop_types.py` | Yes |
| C-XI retry policy | `/review` | 401/403 never retried; tests cover both branches | Yes |
| C-XII config only via `Settings` | `/review` | no `os.environ` / `os.getenv` outside `config.py` (tests' `conftest.py` excepted) | Yes |
| C-XIII constants in `config.py` | `/review` | new constants added to the owning `config.py` | Advisory |
| C-XIV secrets not merged | `/autoplan` eng phase, `/cso` | a new capability gets its own secret | Yes |
| C-XV format validated at startup | `/review` | a new key/URL with a format has a `Settings` validator | Advisory |
| C-XVI tokens encrypted at rest | `/review`, `/cso` | token columns written through `core/crypto.py` | Yes |
| C-XVII two auth axes | `/autoplan` eng phase, `/cso` | caller auth and WHOOP OAuth never substitute for each other | Yes |
| C-XVIII auth scoped to the route | `/review`, `/cso` | per-user routes use `read_token`; `API_KEY` only on fan-out routes | Yes |
| C-XIX structured logging | `/review` | no `print()`; `configure_logging()` only at process start | Yes |
| C-XX contextvars cleared | `/review` | `bind_contextvars` paired with `clear_contextvars` in a `finally` | Yes |
| C-XXI camelCase at the boundary | `/review`, `/qa` | API responses camelCase; Python identifiers snake_case | Yes |
| C-XXII truthful `/health` | `/review`, `/qa`, `/canary` | `/health` returns 503 when Postgres is down, and when Redis is down within `REDIS_HEALTH_TTL_SECONDS`; no other Redis call on the health path; checked after deploy | Yes |
| C-XXIII no speculative infra | `/autoplan` CEO + eng phase | any new infrastructure has a Complexity Tracking row with evidence | Advisory |

## Definition of Done

A feature is done when:

1. Every task in `specs/<NNN-feature>/tasks.md` is checked, or deferred with a reason the owner approved.
2. Every acceptance scenario (`AS-x.y`) in `spec.md` has a passing automated test or a recorded `/qa` pass.
3. `/review` reports no open critical findings.
4. `/ship`'s plan-completion audit shows 0 NOT DONE items,.
5. Every Constitution Check violation in `plan.md` has a justified Complexity Tracking row.
6. `uv run ruff check .`, `uv run mypy .` and `uv run pytest` are clean in every Python service touched, and `npm run build` in `whoop-ui-service/` if it was touched.
7. A schema change says so at the top of its PR description: `alembic upgrade head` is run against Supabase by hand before merge (free-plan Render services don't run `preDeployCommand`).

## Governance

This constitution supersedes other practices in this repo. When a principle changes,
update this file and say why in the commit; don't let code drift away from it
silently.

Amend from evidence: when `/retro` or `/learn` shows the same review finding in two
or more features, propose a new principle or Quality Gates row here, bump the
version, and update Last Amended.

**Version**: 2.1.0 | **Ratified**: 2026-08-17 | **Last Amended**: 2026-10-07
