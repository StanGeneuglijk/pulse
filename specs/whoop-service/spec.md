# Spec: whoop-service

**Status:** built
**Depends on:** WHOOP's developer API

## Summary

Let any number of people connect their own WHOOP account and keep everything WHOOP exposes — cycles, recovery, sleep, workouts, body measurements, profile — synced into the platform's database, so other services can build on it. It is also the platform's identity provider: connecting WHOOP is how a person gets the credential every other service accepts.

## User stories

### US1 — Connect my WHOOP account (P1)

As a WHOOP user, I want to log in with WHOOP and grant read access, so that the platform can sync my data without ever seeing my WHOOP password.

**Independent test:** complete the login flow against a mocked WHOOP; a user exists with encrypted tokens and a per-user credential.

**Acceptance scenarios**

1. **Given** I start login, **when** WHOOP redirects back with a valid code and state, **then** my tokens are stored encrypted and I'm redirected to the frontend with a one-time code — never my credential in the URL.
2. **Given** a callback with a `state` this service didn't issue, **when** it arrives, **then** it's rejected (`400`) and nothing is stored.
3. **Given** I already connected before, **when** I connect the same WHOOP account again, **then** my existing user is updated and keeps the same credential — no duplicate user.
4. **Given** the frontend holds a one-time code, **when** it redeems it once, **then** it receives my user id and credential; **when** it redeems it again, **then** it's rejected.

### US2 — My data stays in sync (P1)

As a connected user, I want my WHOOP data to appear and stay current without doing anything, so that everything built on it is up to date.

**Independent test:** run a sync for one user against mocked WHOOP responses; rows appear; re-running changes nothing.

**Acceptance scenarios**

1. **Given** I just connected, **when** the connect flow finishes, **then** a sync for me is queued immediately.
2. **Given** a sync already ran, **when** the same data is synced again, **then** no row is duplicated and unchanged rows aren't rewritten.
3. **Given** my history spans many pages on WHOOP, **when** I sync for the first time, **then** every page is fetched (up to a bounded history).
4. **Given** my access token expired, **when** a sync runs, **then** it's refreshed and both new tokens are stored.
5. **Given** WHOOP rejects my refresh token (access revoked), **when** a sync runs, **then** I'm marked disconnected and not retried until I reconnect.

### US3 — Sync everyone on a schedule (P1)

As the operator, I want one call to queue a sync for every connected user, so that the platform scales by adding workers, not by making one loop longer.

**Acceptance scenarios**

1. **Given** k connected users, **when** the batch is triggered, **then** k independent jobs are queued and the call returns in well under a second.
2. **Given** a batch was triggered moments ago, **when** it's triggered again, **then** it's rejected (`429`) rather than queuing duplicates.
3. **Given** one user's sync keeps failing, **when** the batch runs, **then** every other user's sync still completes.
4. **Given** WHOOP is down, **when** many jobs run, **then** they fail fast after a threshold of consecutive failures instead of each exhausting its own retries.

### US4 — Read my own data (P2)

As a connected user (through a frontend), I want to read my recovery, sleep and workout records and my recent syncs, and trigger a refresh, so that I can see them.

**Acceptance scenarios**

1. **Given** my own credential, **when** I request my records, **then** I get them; **when** I request someone else's, **then** I get `401`.
2. **Given** nothing changed since my last request, **when** I send the previous `ETag`, **then** I get `304`.
3. **Given** I just pressed refresh, **when** I press it again within a minute, **then** no second job is queued.

## Functional requirements

- **FR-001** Connect via WHOOP OAuth (authorization code) with CSRF `state` and PKCE; scopes: profile, body measurement, cycles, recovery, sleep, workout, offline.
- **FR-001a** Store every metric WHOOP returns: key ones as typed columns, the full record as JSON; tokens granted before a scope existed still sync everything else.
- **FR-002** Identify the WHOOP account on connect; one WHOOP account maps to exactly one user.
- **FR-003** Store WHOOP tokens encrypted at rest; decrypt only at the point of use.
- **FR-004** Issue each user a stable per-user `read_token`; hand it to the frontend only through a single-use, short-lived code.
- **FR-005** Sync one user as a unit of work runnable in any worker process: refresh token if needed → fetch → upsert → record the attempt.
- **FR-006** Every synced record is written idempotently, keyed on (user, WHOOP record id).
- **FR-007** Fetch paginated collections completely (bounded), and incrementally after the first sync.
- **FR-008** Retry transient WHOOP failures with backoff; never retry auth failures.
- **FR-009** Fan a batch out as one job per user; debounce the batch and a user's manual refresh.
- **FR-010** Per-user routes accept the operator key or that user's own `read_token`; the batch route accepts only the operator key.
- **FR-011** Record every sync attempt (status, counts, duration, error) and every read-route hit.
- **FR-012** `/health` reports whether the database and queue are reachable.

## Key entities

- **User** — one WHOOP account: its WHOOP id, encrypted tokens, connection status, `read_token`.
- **Cycle / Recovery / Sleep / Workout** — one WHOOP record each, owned by a user, unique per (user, WHOOP id), with a content fingerprint.
- **Body measurement** — the latest height, weight and max heart rate per user.
- **Sync job log** — one row per sync attempt.
- **Activity log** — one row per read-route hit.
- **Error log** — one row per domain error surfaced over HTTP.

## Success criteria

- **SC-001** Adding workers increases the number of users synced concurrently with no code change.
- **SC-002** Re-running any sync produces zero duplicate rows.
- **SC-003** A batch call for 10,000 users returns in under a second.
- **SC-004** No WHOOP token and no `read_token` ever appears in a URL, a log line, or plaintext in the database.
- **SC-005** The full test suite runs offline (WHOOP mocked) against real Postgres and Redis.

## Out of scope

- Webhooks from WHOOP — scheduled and on-demand sync are enough at this scale.
- Any analysis of the data — that's whoop-insight-service.
- A user interface — that's whoop-ui-service.
- Autoscaling, multi-region, per-tenant fairness (constitution C-XXIII).
