# Implementation Plan: Demo mode

**Branch**: `001-demo-mode` | **Date**: 2026-10-08 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-demo-mode/spec.md`

**Design doc**: none (size M, from a GitHub issue) | **Plan review**: `/plan-eng-review`, 2026-10-08 (kept in the private working repo, not in this copy)

## Summary

Visitors without a WHOOP band get a one-click "Try the demo" on the landing page that puts
them in the real dashboard as a fixed sample person, with a persistent demo banner. The
whole demo lives in `whoop-ui-service`: a demo session is a second kind of value in the
existing session cookie that carries no backend credential. In the demo, the dashboard's
components talk to a browser-side fake of the app's own `/api` routes (`lib/demo/fakeApi.ts`,
reached through `useApiFetch()`) instead of the network: it builds the sample month from a
fixed day-by-day table on every read, so it always ends on the visitor's today, and answers
every AI or WHOOP action with pre-written content. Confirmed meals and goal edits live in its
memory until the page reloads. The three backends, the
database and the sync job don't change, so the demo costs nothing, stores nothing and
cannot reach real data (research R1–R5).

This departs from the spec's original "reuse the existing identity model" assumption; the
owner chose the UI-only design at planning time and spec.md's Assumptions were updated.

## Technical Context

**Language/Version**: TypeScript 5.6, Next.js 14 (App Router), React 18. Node 20 in CI.

**Primary Dependencies**: existing (`next`, `react`, `recharts`, `lucide-react`,
`tailwindcss`); new dev dependency `vitest` (R6).

**Storage**: none. Demo session in the existing `whoop_session` cookie; sample data and
example AI output are code in `lib/demo/`.

**Testing**: Vitest unit tests in `whoop-ui-service/tests/` (new, R6); `/qa` in a browser for
visual and flow scenarios; existing Python suites untouched and must stay green.

**Target Platform**: Render web service (`whoop-ui-service`), modern desktop and mobile
browsers.

**Project Type**: web app (Next.js dashboard in front of three FastAPI services).

**Performance Goals**: landing page → populated demo dashboard in under 10 s once the UI
service is awake (SC-001); the demo itself never waits on a backend.

**Constraints**: no paid AI or WHOOP call from the demo (FR-007, FR-015); nothing stored
(FR-014); real-user paths unchanged (FR-013, regression contract D6); no render.yaml or
hosting change; no new env vars; demo code imported statically (D4: a dynamic chunk can
vanish on redeploy and freeze the demo on its skeleton).

**Scale/Scope**: one persona, 35 days of data, 3 example insights, 1 example meal chat;
about 12 new files and 13 edited ones in `whoop-ui-service`, plus a CI step and docs.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Most principles govern the Python services, which this feature doesn't touch; those rows are
N/A with that evidence. The UI-side analogues are checked where they apply.

| Principle | Status | Evidence in this plan |
|-----------|--------|-----------------------|
| C-I `core/` has no product imports | N/A | No Python service changes (`git diff main -- whoop-service whoop-insight-service whoop-nutrition-service` stays empty). |
| C-II one WHOOP HTTP client | Pass | The demo makes no WHOOP request; `lib/whoopClient.ts` stays the UI's only whoop-service client. `/demo/connect` only redirects the browser to whoop-service's `/auth/login`, like `/login`'s existing link. |
| C-III `api/main.py` only aggregates | N/A | Untouched. UI analogue: `app/demo/*` route handlers only set/clear the cookie and redirect. |
| C-IV `workers/run.py` only boots | N/A | Untouched. |
| C-V no blocking I/O in async | Pass | No new server I/O; demo generation is pure in-browser computation. |
| C-VI explicit `user_id` | Pass | Real-user calls still take `Session` explicitly. The demo has no `user_id` and no ambient identity: `demo` is passed from `app/page.tsx` as a prop into `DemoContext`, whose `useApiFetch()` picks the fake API or the browser's `fetch`; no module-level flag. |
| C-VII upserts only | N/A | No writes anywhere (FR-014). |
| C-VIII jobs by dotted path | N/A | No jobs. |
| C-IX fail fast via domain exceptions | Pass | A demo cookie on any `/api/*` route raises the existing `UnauthenticatedError`, mapped to `401` by `handleRoute` (contracts/demo-routes.md). Malformed or expired demo values read as "no session", same as today's malformed-cookie rule. |
| C-X typed trust boundary | N/A | No new WHOOP fields. Demo data is typed with the existing `lib/types.ts` wire types, so a shape drift fails `npm run typecheck`. |
| C-XI retry policy | N/A | No outbound calls. |
| C-XII config only via `Settings` | Pass | No new env vars. `/demo/connect` reads `WHOOP_SERVICE_URL` through `lib/config.ts`. |
| C-XIII constants in `config.py` | Pass | Demo constants (session hours, days, replay delays) live in one place, the top of `lib/demo/data.ts`. |
| C-XIV secrets not merged | Pass | No new secret; the demo gets no credential at all. |
| C-XV format validated at startup | N/A | No new keys or URLs. |
| C-XVI tokens encrypted at rest | N/A | No tokens stored or issued. |
| C-XVII two auth axes | Pass | Neither WHOOP OAuth nor caller auth is involved in the demo; a demo session substitutes for neither (it is refused by every caller-authenticated route). |
| C-XVIII auth scoped to the route | Pass | Per-user routes still require a real `read_token` session; the demo holds no `read_token` and no `API_KEY`. Proven by `tests/demo/api-guard.test.ts` (AS-3.2). |
| C-XIX structured logging | N/A | No Python process changes; the UI adds no logging. |
| C-XX contextvars cleared | N/A | No per-user Python work. |
| C-XXI camelCase at the boundary | Pass | Demo data uses the same camelCase wire types the backends return. |
| C-XXII truthful `/health` | N/A | `/health` routes untouched. |
| C-XXIII no speculative infra | Pass | No new infrastructure, service or paid plan; one dev dependency (Vitest) justified by R6. |

**Re-check after Phase 1**: unchanged. No violations, so no Complexity Tracking rows.

## Project Structure

### Documentation (this feature)

```text
specs/001-demo-mode/
├── spec.md
├── plan.md              # this file
├── research.md          # R1–R8
├── data-model.md        # demo session, sample person, example AI output
├── quickstart.md        # automated checks + manual walk-through
├── contracts/
│   └── demo-routes.md   # /demo/start, /demo/connect, /api/* refusal rule
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
whoop-ui-service/
├── app/
│   ├── demo/
│   │   ├── start/route.ts      # NEW: set demo cookie (unless real session) → /?demo=started
│   │   └── connect/route.ts    # NEW: clear cookie → whoop-service /auth/login
│   ├── dev/session/route.ts    # EDIT: comment no longer says "seeded demo user" (review Q-1)
│   ├── page.tsx                # EDIT: getCaller(); demo → <Dashboard demo />; cookies-blocked redirect
│   └── login/page.tsx          # EDIT: "Try the demo" button; cookies_blocked message; demo → /
├── lib/
│   ├── session.ts              # EDIT: Caller union, getCaller(), attachDemoCookie(); getSession() decides on `kind`, returns real sessions only
│   ├── useDashboardData.ts     # EDIT: fetch → apiFetch
│   └── demo/
│       ├── data.ts             # NEW: constants, profile, goal, 35-day table (R5), generateDemoData(now)
│       ├── script.ts           # NEW: example insights, meal chat, sync replay
│       ├── fakeApi.ts          # NEW: browser-side fake of every app/api data route; regenerates from new Date() on each read (D5); in-memory confirmed meals/goal until reload; throws on unknown paths (D3)
│       └── DemoContext.tsx     # NEW: provider; useDemo(); useApiFetch() via pure apiFetchFor(demo) (D6); static imports (D4)
├── components/
│   ├── DemoBanner.tsx          # NEW: persistent banner, "Connect your WHOOP", "Leave demo"
│   ├── Dashboard.tsx           # EDIT: demo prop → DemoContext + banner
│   ├── AppShell.tsx            # EDIT: banner slot under the header
│   ├── SyncButton.tsx          # EDIT: fetch → apiFetch
│   ├── UserMenu.tsx            # EDIT: demo → "Leave demo" label (logout stays a real fetch)
│   ├── MealChat.tsx            # EDIT: fetch → apiFetch; in the demo the mic skips getUserMedia and replays the voice exchange; pre-filled example exchange
│   └── tabs/
│       ├── InsightsTab.tsx     # EDIT: fetch → apiFetch
│       └── FuelTab.tsx         # EDIT: fetch → apiFetch (GoalEditor)
├── tests/demo/                 # NEW: session, data, script, fakeApi (parity, state, midnight, isolated, no network), api-guard, regression
├── vitest.config.ts            # NEW
├── package.json                # EDIT: vitest devDependency, "test" script
└── CLAUDE.md                   # EDIT: demo section; /dev/session wording (kept in the private working repo, not in this copy)

.github/workflows/ci.yml        # EDIT: ui job runs npm test
docs/architecture.md            # EDIT: one line — demo sessions stay inside the UI (kept in the private working repo, not in this copy)
docs/knowledge/demo-mode.md     # NEW: why the demo is a fake /api in the browser (kept in the private working repo, not in this copy)
```

**Structure Decision**: Web app; the feature is confined to `whoop-ui-service/` plus CI and
docs. The demo sits behind one seam, `useApiFetch()`: real users get the browser's `fetch`
unchanged, demo visitors get `fakeApi`, so components carry no demo branches beyond the mic
and the banner (review D2). Backends (`whoop-service/`, `whoop-insight-service/`, `whoop-nutrition-service/`)
are deliberately untouched.

## Test Strategy

All Verify commands run from `whoop-ui-service/`.

| Scenario | Test level | Test location | Verify command |
|----------|------------|---------------|----------------|
| AS-1.1 | unit + manual via /qa | `tests/demo/routes.test.ts` (start route sets demo cookie, redirects to `/?demo=started`); /qa clicks "Try the demo" | `npx vitest run tests/demo/routes.test.ts -t "start"` |
| AS-1.2 | manual via /qa | every tab in a demo session | /qa |
| AS-1.3 | unit | `tests/demo/data.test.ts::ends today` (offset 0 is local today for several `now` values incl. 00:05 and 23:55; ≥30 consecutive days); `tests/demo/fakeApi.test.ts::midnight` (a read after midnight moves "today", confirmed meal kept, D5) | `npx vitest run tests/demo/data.test.ts tests/demo/fakeApi.test.ts -t "today|midnight"` |
| AS-1.4 | unit + /qa | `tests/demo/data.test.ts::meals and goal` | `npx vitest run tests/demo/data.test.ts -t "meals"` |
| AS-1.5 | manual via /qa | banner on every tab; "Connect your WHOOP" → `/demo/connect` → whoop-service login | /qa; `npx vitest run tests/demo/routes.test.ts -t "connect"` |
| AS-1.6 | unit + /qa | `tests/demo/routes.test.ts::leave` (logout clears demo cookie; `/` then redirects) | `npx vitest run tests/demo/routes.test.ts -t "leave"` |
| AS-2.1 | unit + /qa | `tests/demo/script.test.ts::insight numbers match data` | `npx vitest run tests/demo/script.test.ts -t "insight"` |
| AS-2.2 | unit + /qa | `tests/demo/script.test.ts::meal chat` (proposal totals = sum of items) | `npx vitest run tests/demo/script.test.ts -t "meal chat"` |
| AS-2.3 | unit + /qa | `tests/demo/fakeApi.test.ts::no network` (a full demo session through fakeApi never calls the global `fetch`); `tests/demo/api-guard.test.ts`; /qa network log empty | `npx vitest run tests/demo` |
| AS-2.4 | manual via /qa | Generate, send, suggestion, mic, refresh in the demo: pre-written result, no error | /qa |
| AS-2.5 | unit + /qa | `tests/demo/fakeApi.test.ts::state` (confirm shows in meals list, discard doesn't, goal PUT shows in GET; a new fakeApi instance starts clean); /qa reload | `npx vitest run tests/demo/fakeApi.test.ts -t "state"` |
| AS-3.1 | unit + /qa | `tests/demo/fakeApi.test.ts::isolated` (two instances don't share state); /qa two browsers | `npx vitest run tests/demo/fakeApi.test.ts -t "isolated"` |
| AS-3.2 | unit | `tests/demo/api-guard.test.ts` (every `app/api/**/route.ts` handler with a demo cookie → 401, `fetch` never called) | `npx vitest run tests/demo/api-guard.test.ts` |
| AS-3.3 | unit + /qa | `tests/demo/session.test.ts::real session unchanged` (legacy cookie still a real session); `tests/demo/regression.test.ts` (`apiFetchFor(false) === globalThis.fetch`; source scan: no bare `fetch('/api/…')` under `components/` or `lib/` except `UserMenu`'s logout, D6); /qa as a real user | `npx vitest run tests/demo/session.test.ts tests/demo/regression.test.ts` |
| AS-3.4 | static | backends untouched, so the sync fan-out can't see a sample person | `git diff --quiet main -- whoop-service whoop-insight-service whoop-nutrition-service` |
| AS-3.5 | unit + /canary | same as AS-2.3, plus provider usage unchanged after deploy | `npx vitest run tests/demo` |

**Drift guard** (D3): `tests/demo/fakeApi.test.ts::parity` lists every `app/api/**/route.ts`
(except `health` and `auth/logout`) and its exported methods, and fails if `fakeApi` has no
handler for one.

**Full suite**: `npm test && npm run typecheck && npm run build` in `whoop-ui-service/`;
`uv run pytest` in the three Python services stays green with no changes.

## Delivery & Distribution

**Ships as**: a new version of the `whoop-ui-service` Render web service. No backend deploy
has any change, no migration.

**Deploy path**: PR → CI (`ui` job now also runs `npm test`) → squash merge to `main` →
Render auto-deploys all services (backends redeploy unchanged).

**Post-deploy checks** (for `/canary`):
- `GET https://whoop-ui.onrender.com/login` returns 200 and contains "Try the demo".
- `GET https://whoop-ui.onrender.com/demo/start` returns a redirect to `/?demo=started` with
  a `whoop_session` cookie; following it renders the dashboard with the demo banner.
- With that cookie, `GET /api/whoop/recovery` returns 401.
- Each API's `/health` returns 200 and `/version` returns the merge commit.
- Anthropic and OpenAI usage dashboards show no change attributable to the demo.

**Rollback**: revert the merge commit. Nothing is stored, so there is nothing to clean up;
open demo cookies simply read as "no session" on the old code and land on `/login`.

## Review Outcomes *(from /autoplan)*

**Review run**: `/plan-eng-review` on spec.md + plan.md (kept in the private working repo, not in this copy) — 2026-10-08, `/plan-eng-review` (size M), 4 issues, all resolved; outside voice unavailable (Codex not installed)

| Decision | Source | Applied to |
|----------|--------|------------|
| D2: demo runs on a browser-side fake of the app's `/api` behind `useApiFetch()`, not demo branches in six components | eng review, Scope Challenge (structure) | plan.md §Summary, §Source Code; research.md R4 |
| D3: route-parity test between `app/api/**/route.ts` and `fakeApi`; `fakeApi` throws on unknown paths | eng review, Scope Challenge (SC-1) | plan.md §Test Strategy; tasks.md |
| D4: demo code imported statically, no dynamic chunk | eng review, Architecture (A-1) | plan.md §Technical Context; research.md R2 |
| D5: `fakeApi` regenerates from `new Date()` on every read; in-page changes stored as day offsets | eng review, Architecture (A-2) | plan.md §Test Strategy; data-model.md |
| D6: real-user regression contract: `apiFetchFor(false) === globalThis.fetch` + source scan for bare `/api` fetches (logout excepted) + /qa | eng review, Test review (T-1) | plan.md §Test Strategy (AS-3.3); tasks.md |
| Q-1: reword `/dev/session`'s "seeded demo user" comment | eng review, Code quality | plan.md §Source Code |

**Deferred** (not in this feature): none

## Complexity Tracking

No Constitution Check violations.

## Build Notes

<!-- /sdd-build appends here. -->

- 2026-10-12 T015 `vitest.config.ts` sets `esbuild: { jsx: "automatic" }`: Vitest's default classic JSX runtime fails on the app's components (`React is not defined`), which Next compiles with the automatic runtime.
- 2026-10-12 T021 `fakeApi` stores a confirmed demo meal with the absolute time it was confirmed, not a day offset (review D5 said offsets): the sample table still rebuilds from the current time on every read, and a meal confirmed at 23:50 correctly stays on that day after midnight instead of jumping to the new today.
