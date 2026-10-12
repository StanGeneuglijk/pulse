# Research: Demo mode

Phase 0 of `/speckit-plan`. Each decision: what was chosen, why, and what else was considered.
No `NEEDS CLARIFICATION` remained in Technical Context after these.

## R1. Where the demo lives: dashboard app only

**Decision**: The whole demo lives in `whoop-ui-service`. No backend, database, migration,
sync or spend-accounting change. The sample person exists only as code in the dashboard
app; the backends never see a demo request.

**Rationale**:
- Spec FR-010/FR-012/FR-014 and AS-3.2/3.4/3.5 become true by construction instead of by
  special cases: there is no sample-person row to sync, count or spend against, no demo
  credential that could be widened, and nothing stored that grows with visits.
- FR-013 (real users unchanged) is easiest to keep when no real-user code path in the
  three backends changes at all.
- Owner chose this at planning time (2026-10-08) over the spec's original "reuse the
  existing identity model" assumption; spec.md's Assumptions were updated to match.

**Alternatives considered**:
- *Seeded backend user with a demo `read_token`*: needs rolling dates (daily reseed job or
  a read-time date shift), scripted-replay branches inside insight and nutrition services,
  exclusion from `sync_batch` and spend accounting, and a migration. Every service changes
  and the auth path gains a special case (C-XVIII risk). Rejected: more surface, more risk
  to real users, no visitor-visible benefit.

## R2. Where the sample data is generated: in the browser, in local time

**Decision**: `lib/demo/data.ts` generates the sample person's `DashboardData` in the
browser from `new Date()`, using the visitor's local calendar. `lib/demo/fakeApi.ts` calls it
on every read, so a tab left open past midnight moves to the new day on its next refresh
(review D5). The demo code is imported statically (review D4): a dynamic chunk can disappear
on a redeploy and leave the demo stuck on its loading skeleton; the cost is an estimated
10–25 KB for every visitor.

**Rationale**: The dashboard decides "today" with the browser's local calendar
(`lib/format.ts` `isToday`, `dayKey`; `lib/nutrition.ts` `mealsOn`). Data generated on the
server in UTC would put "today's" recovery on yesterday for part of the day in many time
zones (AS-1.3 fails around local midnight). Generating it where "today" is decided removes
the mismatch.

**Alternatives considered**:
- *Server `/api/*` routes answer demo sessions with sample data*: keeps components
  unchanged, but the server doesn't know the visitor's time zone (a plain link click
  carries none). Rejected for AS-1.3.
- *Anchor records to "now minus N hours"*: still breaks shortly after local midnight, and
  puts sleep ends at odd times of day.

## R3. Demo session: a second kind of value in the same cookie

**Decision**: The existing `whoop_session` cookie carries either a real session
(`{userId, readToken}`, unchanged) or a demo session (`{kind: "demo", exp}`).
`lib/session.ts` gains `getCaller()` returning `user | demo | null`; `getSession()` /
`requireSession()` keep returning only real sessions. Demo cookies last 24 hours (`maxAge`
plus an `exp` checked on read).

**Rationale**:
- One cookie means the two identities can never coexist: starting a demo can't sit on top
  of a real session, and a real login overwrites a demo (spec edge cases).
- Because `requireSession()` never accepts a demo value, every existing `app/api/*` route
  answers a demo session `401` before it can build a backend request. That is the
  server-side guard for AS-3.2 and FR-007, and it needs no per-route change.
- Unsigned, like the real cookie (see `whoop-ui-service/lib/session.ts`): forging a demo value
  only gets you the public demo; forging `exp` only extends it.
- Cookies without `kind` keep parsing as real sessions, so nobody is logged out by the
  deploy.

**Alternatives considered**:
- *Separate `whoop_demo` cookie*: both could be present at once, which needs precedence
  rules. Rejected.
- *Signed/encrypted demo cookie*: protects nothing (R3 rationale). Rejected.

## R4. Scripted replay: a fake of the app's own /api, in the browser

**Decision** (revised by the plan review, D2): `Dashboard` receives `demo` from the server
page and provides a `DemoContext`. Components get their fetch function from
`useApiFetch()`: real users get the browser's `fetch` unchanged; demo visitors get
`lib/demo/fakeApi.ts`, which answers every `app/api` data route the dashboard uses with
sample data and pre-written content from `lib/demo/script.ts` (example insight per period,
Generate after a short "reading" delay, the example meal exchange, a pretend sync). Confirmed
meals and goal edits live in `fakeApi`'s memory until the page reloads. The only component
branches left: `MealChat`'s mic skips `getUserMedia` and replays the voice exchange, and the
banner / "Leave demo" label. `UserMenu`'s logout stays a real request in both modes.

**Rationale**: The visitor's clicks never produce a network request in the demo, so there is
nothing to fail (AS-2.4 "never shows an error") and nothing to save (AS-2.5). Skipping
`getUserMedia` avoids a microphone permission prompt for a recording nobody uses.

**Alternatives considered**:
- *One demo branch inside each interactive component* (the original plan): six branches in
  real-user code, and "reload after confirm" would wipe in-page changes. Rejected in review.
- *Server routes replay scripts*: rejected with R2.

**Guards** (review D3, D6): a parity test fails when an `app/api` route has no `fakeApi`
handler; a regression test pins `apiFetchFor(false)` to the browser's `fetch` and scans for
any bare `fetch('/api/…')` left in components (logout excepted).

## R5. Sample data is a fixed day-by-day table, not random

**Decision**: `lib/demo/data.ts` holds a hand-written 35-day table (day offset → recovery,
HRV, RHR, sleep stages, strain, workout, meals). The generator maps offset 0 to the
visitor's today. Same numbers every day; only the dates move.

**Rationale**: The example insights quote the sample person's actual numbers (AS-2.1). A
fixed table lets them be written once and checked by a test that reads the same table.
The table encodes a story (FR-004): a hard three-day training block around days −6…−4,
recovery dipping to red/yellow, then rebounding to green today.

**Alternatives considered**: *Seeded random walk*: plausible, but insight text could no
longer quote exact numbers. Rejected.

## R6. Tests: add Vitest to the dashboard app

**Decision**: Add `vitest` as a dev dependency of `whoop-ui-service`, an `npm test`
script, a `vitest.config.ts` with the `@/` alias, and an `npm test` step in CI's `ui` job.
Tests live in `whoop-ui-service/tests/`.

**Rationale**: The app has no test runner today, and AS-1.3, AS-2.1, AS-2.3 and AS-3.2 are
best proven by automated tests (data window ends today, insight numbers match data, demo
replay never calls `fetch`, every `/api/*` route refuses a demo session without calling a
backend). Pure modules need no DOM, so tests stay fast and offline.

**Alternatives considered**: *Only `/qa` browser checks*: can't prove "no backend call" or
"refused for every route" exhaustively. *Playwright*: heavier; `/qa` already drives a real
browser for the visual scenarios.

## R7. Cookies blocked and expired demo

**Decision**: `GET /demo/start` sets the cookie and redirects to `/?demo=started`. If the
page then finds no session and sees that marker, it redirects to
`/login?error=cookies_blocked` ("The demo needs cookies…"). An expired demo cookie reads as
no session, so the visitor lands on the landing page (`/login`) as today.

**Rationale**: Covers both spec edge cases with no client JS.

## R8. Leaving the demo and connecting from it

**Decision**: "Leave demo" reuses `POST /api/auth/logout` (clears the cookie) and goes to
`/login`. "Connect your WHOOP" goes to `GET /demo/connect`, which clears the demo cookie and
redirects to whoop-service's `/auth/login`.

**Rationale**: AS-1.6 and the "identities never mix" edge case, with one new route.
