---

description: "Task list for 001-demo-mode (gstack-sdd)"
---

# Tasks: Demo mode

**Input**: Design documents from `/specs/001-demo-mode/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/demo-routes.md, quickstart.md, and the plan review (`/plan-eng-review`, 2026-10-08; its record is kept in the private working repo, not in this copy)

**Tests**: Test-first. Every user-story phase starts with test tasks that must FAIL before the implementation tasks after them. All Verify commands run from the repo root.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

**State**: This file is the build state. `/sdd-build` resumes at the first unchecked task, ticks `[x]` after a task's Verify passes, and commits code and this file together. Don't keep a second task list anywhere else.

## Format: `- [ ] [ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies). `/sdd-build` hands `[P]` tasks to parallel subagents.
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- **Source**: `FR-xxx` / `AS-x.y` from spec.md, `C-xx` from the constitution, `REV-eng-T<n>` from the plan review's task list, or `BUILD` if added during build.
- **Verify**: One local, fast command (or a precise manual check) that proves the task is done.

**Checkpoint gates are NOT checkboxes.**

## Path Conventions

Everything lives in `whoop-ui-service/` (Next.js 14 App Router) unless a path says otherwise. Tests live in `whoop-ui-service/tests/demo/`. The three Python services are not touched by this feature.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: A test runner for the dashboard app (research R6) and CI that runs it.

- [x] T001 Add Vitest to whoop-ui-service: `vitest` devDependency in whoop-ui-service/package.json, a `"test": "vitest run"` script, and whoop-ui-service/vitest.config.ts with `environment: "node"`, `include: ["tests/**/*.test.ts"]` and the `@/` → project-root alias matching tsconfig.json's `"paths": { "@/*": ["./*"] }`
  - Source: plan.md §Technical Context (Testing), research.md R6
  - Verify: `cd whoop-ui-service && npm install && npm test -- --passWithNoTests && npm run typecheck`
- [x] T002 [P] Add an `npm test` step to the `ui` job in .github/workflows/ci.yml, after `npm ci` and before `npm run typecheck`
  - Source: plan.md §Delivery & Distribution, research.md R6
  - Verify: `grep -n "npm test" .github/workflows/ci.yml`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The demo session kind and the one seam (`useApiFetch()`) every story builds on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T003 [P] Write whoop-ui-service/tests/demo/session.test.ts (mock `next/headers` `cookies()` with a `vi.hoisted` Map): a legacy cookie `{userId, readToken}` with no `kind` → `getCaller()` is `{kind:"user", session}` and `getSession()` returns it unchanged ("real session unchanged"); `{kind:"demo", exp: now+1h}` → `getCaller()` is `{kind:"demo"}` and `getSession()` returns null and `requireSession()` throws `UnauthenticatedError`; "A demo value past `exp` reads as no session" → `getCaller()` null; malformed base64/JSON → null; `attachDemoCookie()` sets `whoop_session` with `httpOnly`, `sameSite: "lax"`, `path: "/"` and `maxAge` 24 h, and an `exp` 24 h ahead
  - Source: AS-3.3, FR-010, FR-014, data-model.md §Demo session
  - Verify: `cd whoop-ui-service && npx vitest run tests/demo/session.test.ts` fails before T004, passes after
- [x] T004 Extend whoop-ui-service/lib/session.ts: `Caller = {kind:"user"; session: Session} | {kind:"demo"} | null`, `getCaller()`, `attachDemoCookie(response)`; `getSession()` decides on the `kind` discriminant explicitly and returns real sessions only (so `requireSession()` never returns a demo); the demo value holds **no** `userId` and **no** `readToken`; `DEMO_SESSION_HOURS = 24` read from whoop-ui-service/lib/demo/data.ts (create that file with just the constants block for now)
  - Source: FR-010, FR-014, data-model.md §Demo session, research.md R3, C-XVIII
  - Verify: `cd whoop-ui-service && npx vitest run tests/demo/session.test.ts && npm run typecheck`
- [x] T005 [P] Write whoop-ui-service/tests/demo/regression.test.ts, part 1: `apiFetchFor(false, fake)` returns `globalThis.fetch` itself (real users' requests unchanged); `apiFetchFor(true, fake)` returns `fake.fetch` and never the global one
  - Source: REV-eng-T5 (P1), AS-3.3, FR-013
  - Verify: `cd whoop-ui-service && npx vitest run tests/demo/regression.test.ts` fails before T006, passes after
- [x] T006 Create whoop-ui-service/lib/demo/fakeApi.ts skeleton (`createFakeApi(now: () => Date)` returning `{ fetch }` with a fetch-compatible signature that matches method + pathname against a handler table and **throws** `Error("demo: no handler for <METHOD> <path>")` on unknown paths) and whoop-ui-service/lib/demo/DemoContext.tsx (`"use client"`; `DemoProvider({demo, children})` creating one fakeApi instance per mount; `useDemo(): boolean`; `useApiFetch()` wrapping the pure exported `apiFetchFor(demo, fake)`; demo modules imported **statically**, no dynamic `import()`)
  - Source: REV-eng-T1 (P1), REV-eng-T3 (P2), REV-eng-T5 (P1), research.md R4, C-VI
  - Verify: `cd whoop-ui-service && npx vitest run tests/demo/regression.test.ts && npm run typecheck`

> **Checkpoint**: Foundation ready. `npm test`, `npm run typecheck` and `npm run build` pass. User story phases can now start.

---

## Phase 3: User Story 1 - Explore the dashboard without WHOOP (Priority: P1) 🎯 MVP

**Goal**: One click from the landing page into the real dashboard as the sample person, every tab populated, persistent demo banner with "Connect your WHOOP" and "Leave demo". View-only is acceptable for this story; scripted actions come in US2.

**Independent Test**: In a fresh browser with no session, open the landing page, click "Try the demo", and visit every tab. Every tab shows sample data, the demo banner stays visible, and no WHOOP login was needed.

### Tests for User Story 1 (write first, see them FAIL)

- [x] T007 [P] [US1] Write whoop-ui-service/tests/demo/data.test.ts for `generateDemoData(now)`: "ends today": for `now` at local 00:05, 12:00 and 23:55, offset 0's recovery, main sleep and cycle fall on `now`'s local calendar day, and at least 30 consecutive days have recovery, sleep and cycle; ranges "Recovery 1–99, HRV 20–150 ms, RHR 40–80 bpm, sleep 4–10 h with stages summing to time asleep, strain 0–21, kJ > 0, meal macros ≥ 0 and kcal ≈ 4·P + 4·C + 9·F (±15%)"; "meals": meals on at least 24 of the last 30 days and one active goal; "story": offsets −6…−4 strain ≥ 16, recovery < 50 on at least one of −5…−3, recovery ≥ 67 on offset 0; record ids stable (`demo-rec-<offset>`)
  - Source: AS-1.3, AS-1.4, FR-003, FR-004, FR-005
  - Verify: `cd whoop-ui-service && npx vitest run tests/demo/data.test.ts` fails before T011, passes after
- [x] T008 [P] [US1] Write whoop-ui-service/tests/demo/script.test.ts, part 1 "insight": for each of daily, weekly and monthly there is an example insight, and every number quoted in its text appears in (or is computed from, e.g. a 7-day average) `generateDemoData`'s table for that period
  - Source: AS-1.2, AS-2.1, FR-006
  - Verify: `cd whoop-ui-service && npx vitest run tests/demo/script.test.ts -t "insight"` fails before T012, passes after
- [x] T009 [P] [US1] Write whoop-ui-service/tests/demo/routes.test.ts (mock `next/headers` and `next/navigation` `redirect`): `GET /demo/start` with a real session → 307 to `/` and cookie untouched; with no session or a demo session → sets a fresh demo `whoop_session` and 307 to `/?demo=started`; "connect": `GET /demo/connect` clears `whoop_session` and 307s to `${WHOOP_SERVICE_URL}/auth/login`; `app/page.tsx`: user → renders Dashboard, demo → renders Dashboard with `demo`, none → redirect `/login`, none + `?demo=started` → redirect `/login?error=cookies_blocked`; `app/login/page.tsx`: demo or real session → redirect `/`; "leave": after `POST /api/auth/logout` clears the demo cookie, `/` redirects to `/login`
  - Source: AS-1.1, AS-1.5, AS-1.6, contracts/demo-routes.md, spec.md Edge Cases (cookies blocked, real session present, connect from demo)
  - Verify: `cd whoop-ui-service && npx vitest run tests/demo/routes.test.ts` fails before T014–T015, passes after
- [x] T010 [P] [US1] Write whoop-ui-service/tests/demo/fakeApi.test.ts, part 1 "reads": through `createFakeApi(() => now).fetch`, every GET the dashboard loads (`/api/whoop/recovery`, `/sleep`, `/workout`, `/cycles`, `/profile`, `/syncs`, `/api/nutrition/meals/list?days=30`, `/api/nutrition/goal`, `/api/insight/latest?period=…`, `/api/insight/list?period=…`, `/api/insight/usage`) returns 200 JSON in the `lib/types.ts` shapes, `insight/latest` is non-empty for all three periods, `insight/usage` reports `spendUsd: 0`; "no network": a `vi.spyOn(globalThis, "fetch")` is never called; "midnight": with a clock at 23:59 then 00:01 the next day, `/api/whoop/recovery`'s newest record moves to the new local day (data rebuilt on every read)
  - Source: AS-1.2, AS-1.3, AS-2.3, REV-eng-T4 (P2), FR-007, FR-015
  - Verify: `cd whoop-ui-service && npx vitest run tests/demo/fakeApi.test.ts -t "reads|no network|midnight"` fails before T013, passes after

### Implementation for User Story 1

- [x] T011 [US1] Complete whoop-ui-service/lib/demo/data.ts: constants block (`DEMO_SESSION_HOURS`, `DEMO_DAYS = 35`, replay delays), fixed fictional `Profile`, active `NutritionGoal` (e.g. `muscle_gain`, 2,600 kcal, 160 g protein), the hand-written 35-row day table (research R5 story: hard block on −6…−4, dip, green today), and `generateDemoData(now: Date): DashboardData` mapping rows to `lib/types.ts` wire types on the visitor's local calendar, with one `syncs` entry a few minutes before `now`
  - Source: FR-002, FR-003, FR-004, FR-005, AS-1.3, AS-1.4, research.md R2/R5, C-XIII, C-XXI
  - Verify: `cd whoop-ui-service && npx vitest run tests/demo/data.test.ts`
- [x] T012 [US1] Create whoop-ui-service/lib/demo/script.ts with the three example insights (daily, weekly, monthly), written about the day table and quoting its numbers, exposed as `exampleInsight(period, now): InsightRecord` with period dates from `now` and `modelName: "example (demo)"`
  - Source: FR-006, AS-1.2, AS-2.1
  - Verify: `cd whoop-ui-service && npx vitest run tests/demo/script.test.ts -t "insight"`
- [x] T013 [US1] Add the read handlers to whoop-ui-service/lib/demo/fakeApi.ts (the GET routes listed in T010), each calling `generateDemoData(now())` on every request; `insight/latest` returns `exampleInsight`, `insight/list` returns `[exampleInsight]`, `insight/usage` returns zero spend
  - Source: AS-1.2, AS-1.3, AS-1.4, FR-007, REV-eng-T1 (P1), REV-eng-T4 (P2)
  - Verify: `cd whoop-ui-service && npx vitest run tests/demo/fakeApi.test.ts -t "reads|no network|midnight"`
- [x] T014 [P] [US1] Create whoop-ui-service/app/demo/start/route.ts (real session → 307 `/`; otherwise `attachDemoCookie` and 307 `/?demo=started`, using `publicUrl`) and whoop-ui-service/app/demo/connect/route.ts (`clearSessionCookie`, 307 to `${config.whoopServiceUrl}/auth/login` via `lib/config.ts`)
  - Source: FR-001, AS-1.1, AS-1.5, contracts/demo-routes.md, C-XII
  - Verify: `cd whoop-ui-service && npx vitest run tests/demo/routes.test.ts -t "start|connect"`
- [x] T015 [US1] Update whoop-ui-service/app/page.tsx (`getCaller()`; user → `<Dashboard />`, demo → `<Dashboard demo />`, none → `/login`, none + `demo=started` → `/login?error=cookies_blocked`) and whoop-ui-service/app/login/page.tsx (any caller → `/`; a "Try the demo" link to `/demo/start` next to "Connect WHOOP", no form; `cookies_blocked` message: "The demo needs cookies — allow them for this site and try again.")
  - Source: FR-001, AS-1.1, AS-1.6, spec.md Edge Cases (cookies blocked, real session present)
  - Verify: `cd whoop-ui-service && npx vitest run tests/demo/routes.test.ts`
- [x] T016 [US1] Replace `fetch` with `useApiFetch()` in whoop-ui-service/lib/useDashboardData.ts, components/tabs/InsightsTab.tsx, components/MealChat.tsx, components/tabs/FuelTab.tsx (GoalEditor) and components/SyncButton.tsx; leave components/UserMenu.tsx's `fetch("/api/auth/logout")` a real request; add part 2 of whoop-ui-service/tests/demo/regression.test.ts: a source scan that fails on any bare `fetch(` with an `/api/` URL under `components/` or `lib/` except UserMenu's logout
  - Source: REV-eng-T5 (P1), REV-eng-T1 (P1), AS-3.3, FR-013
  - Verify: `cd whoop-ui-service && npx vitest run tests/demo/regression.test.ts && npm run typecheck`
- [x] T017 [US1] Wire the demo UI: whoop-ui-service/components/Dashboard.tsx takes `demo?: boolean` and wraps its tree in `DemoProvider`; new whoop-ui-service/components/DemoBanner.tsx (persistent, not dismissible: "Demo · sample data", a "Connect your WHOOP" link to `/demo/connect`, a "Leave demo" button that POSTs `/api/auth/logout` then goes to `/login`); whoop-ui-service/components/AppShell.tsx renders the banner under the header when `useDemo()`; whoop-ui-service/components/UserMenu.tsx shows "Leave demo" instead of "Log out" in the demo
  - Source: FR-009, AS-1.5, AS-1.6, AS-3.3 (no banner for real users)
  - Verify: `cd whoop-ui-service && npm run typecheck && npm run build`; manual: `npm run dev`, open `/login` → Try the demo → banner on all six tabs; a real `/dev/session` login shows no banner

> **Checkpoint — User Story 1 gate** (run by `/sdd-build`, not a checkbox):
> `npm test`, typecheck and build pass; AS-1.1–AS-1.6 pass (tests above + a manual click-through of all six tabs in `npm run dev`); then you choose: continue to US2, ship US1 now (MVP, view-only demo), stop, or revise the spec.

---

## Phase 4: User Story 2 - See what the AI does, without paying for it (Priority: P2)

**Goal**: Every AI or WHOOP action in the demo plays a pre-written result (Generate, chat, mic, Refresh, confirm/discard, goal), nothing is saved, and no paid call is made.

**Independent Test**: Start a demo, open Insights and switch between daily, weekly and monthly; open Fuel and read the example chat. Check the AI providers' usage: it hasn't moved.

### Tests for User Story 2 (write first, see them FAIL)

- [x] T018 [P] [US2] Extend whoop-ui-service/tests/demo/fakeApi.test.ts, part 2 "state" (with `vi.useFakeTimers()` for replay delays): `POST /api/insight/generate {period}` resolves to that period's example insight; `POST /api/nutrition/chat` returns `{conversationId, reply, pendingMeal}` with the example proposal whatever the message; `POST /api/nutrition/chat/audio` returns the same plus `transcript` = the example's spoken text; `POST /api/nutrition/meals/confirm` → the meal then appears in `meals/list` for today; `POST /api/nutrition/meals/discard` → it doesn't; `PUT /api/nutrition/goal` → `GET` returns the new goal; `POST /api/whoop/sync` → `{queued: true}` and `syncs[0]` is "just now"; a confirmed meal survives a read after midnight; a new `createFakeApi` instance starts from the original state; none of these ever returns a non-2xx
  - Source: AS-2.2, AS-2.4, AS-2.5, FR-008, REV-eng-T4 (P2)
  - Verify: `cd whoop-ui-service && npx vitest run tests/demo/fakeApi.test.ts -t "state"` fails before T021, passes after
- [x] T019 [US2] Extend whoop-ui-service/tests/demo/fakeApi.test.ts, part 3 "parity": list every `whoop-ui-service/app/api/**/route.ts` except `app/api/health` and `app/api/auth/logout`, read its exported HTTP methods, and fail if `fakeApi` has no handler for that method + path; a request to an unknown path throws
  - Source: REV-eng-T2 (P1), FR-008
  - Verify: `cd whoop-ui-service && npx vitest run tests/demo/fakeApi.test.ts -t "parity"` fails before T021, passes after
- [x] T020 [P] [US2] Extend whoop-ui-service/tests/demo/script.test.ts, part 2 "meal chat": the example proposal's `totalCalories`, `totalProteinG`, `totalCarbsG`, `totalFatG` equal the sums of its items; the pre-filled exchange is user message → assistant reply with the proposal → a final "Logged ✓ <description> — <kcal> kcal" line
  - Source: AS-2.2, FR-006
  - Verify: `cd whoop-ui-service && npx vitest run tests/demo/script.test.ts -t "meal chat"` fails before T021, passes after

### Implementation for User Story 2

- [x] T021 [US2] Add to whoop-ui-service/lib/demo/script.ts the example meal-chat exchange (`userText`, spoken `transcript`, `reply`, `MealProposal` with items) and the pre-filled entries; add to whoop-ui-service/lib/demo/fakeApi.ts the write handlers from T018 with in-memory state (confirmed meals stored relative to the day and re-applied on every read, goal override, last-sync time) and the replay delays from `lib/demo/data.ts`
  - Source: FR-006, FR-008, AS-2.2, AS-2.4, AS-2.5, REV-eng-T2 (P1), REV-eng-T4 (P2)
  - Verify: `cd whoop-ui-service && npx vitest run tests/demo/fakeApi.test.ts tests/demo/script.test.ts`
- [x] T022 [US2] Update whoop-ui-service/components/MealChat.tsx: when `useDemo()`, start with the pre-filled example exchange, and the mic button replays the voice exchange (sends a request through `apiFetch` to `/api/nutrition/chat/audio` with an empty blob) **without** calling `navigator.mediaDevices.getUserMedia`; real users unchanged
  - Source: AS-2.2, AS-2.4, FR-007, FR-013
  - Verify: `cd whoop-ui-service && npm run typecheck && npx vitest run tests/demo/regression.test.ts`; manual: in the demo, the Fuel chat is pre-filled and the mic replays with no permission prompt
- [x] T023 [US2] Manual scripted-replay check in `npm run dev` (whoop-ui-service): in the demo, Generate on daily/weekly/monthly, send a message, click a suggestion, use the mic, confirm (Fuel totals update), discard, change the goal, click Refresh: every action shows a pre-written result, no error banner, and DevTools Network shows no `/api/*` request; reload → original state
  - Source: AS-2.1, AS-2.2, AS-2.3, AS-2.4, AS-2.5
  - Verify: manual check as described; record the result in the US2 checkpoint

> **Checkpoint — User Story 2 gate**: full suite passes; AS-2.1–AS-2.5 pass; US1 scenarios still pass; then you choose how to continue.

---

## Phase 5: User Story 3 - Many visitors at once, real users untouched (Priority: P3)

**Goal**: Prove isolation: a demo session can't reach real data or any backend, visitors don't affect each other, the backends and sync are untouched.

**Independent Test**: Run two demo sessions in two browsers side by side and act in one; the other is unchanged. In a demo session, try to request a real user's data directly; it is refused. Sign in as a real user; everything behaves as before.

### Tests for User Story 3

- [x] T024 [P] [US3] Write whoop-ui-service/tests/demo/api-guard.test.ts: for every `app/api/**/route.ts` except `app/api/health` and `app/api/auth/logout`, call each exported handler with a demo `whoop_session` cookie (mocked `next/headers`) and a minimal `NextRequest` (for `app/api/nutrition/chat/audio`, a multipart body with an `audio` Blob, because that route calls `request.formData()` before `requireSession()`), and assert status 401 with `{"error": "Not authenticated"}` and that a `globalThis.fetch` spy was never called
  - Source: AS-3.2, AS-3.5, FR-007, FR-010, FR-015, C-XVIII, SC-004
  - Verify: `cd whoop-ui-service && npx vitest run tests/demo/api-guard.test.ts`
- [x] T025 [P] [US3] Extend whoop-ui-service/tests/demo/fakeApi.test.ts, part 4 "isolated": two `createFakeApi` instances; confirming a meal, changing the goal and syncing in one leaves the other's responses identical to a fresh instance
  - Source: AS-3.1, FR-011
  - Verify: `cd whoop-ui-service && npx vitest run tests/demo/fakeApi.test.ts -t "isolated"`
- [x] T026 [US3] Confirm the backends are untouched, so batch sync, spend accounting and user counts can't see a sample person
  - Source: AS-3.4, AS-3.5, FR-012
  - Verify: `git diff --quiet main -- whoop-service whoop-insight-service whoop-nutrition-service && echo untouched`

> **Checkpoint — User Story 3 gate**: full suite passes; AS-3.1–AS-3.5 pass (AS-3.3 also by a real-user click-through: no banner, sync/insight/chat work as before); US1 and US2 scenarios still pass.

---

## Phase R: Review Findings (from /plan-eng-review)

**Purpose**: Every P1/P2 task from the plan review's task list is folded into a story or foundational task above:

- REV-eng-T1 (P1, fake API behind `useApiFetch`): T006, T013, T016
- REV-eng-T2 (P1, route-parity test): T019, T021
- REV-eng-T3 (P2, static import): T006
- REV-eng-T4 (P2, dates rebuilt on every read): T010, T013, T018, T021
- REV-eng-T5 (P1, real-user regression contract): T005, T006, T016
- REV-eng-T6 (P3, `/dev/session` wording): already planned work in plan.md §Source Code, done in T027

---

## Phase N: Polish & Cross-Cutting Concerns

**Purpose**: Docs and the full validation pass.

- [x] T027 [P] Update docs: the service working notes (a "Demo mode" section), the architecture map and a concept note on why the demo is a fake `/api` in the browser (kept in the private working repo, not in this copy)
  - Source: project docs rule (docs follow every design change), REV-eng-T6 (P3), plan.md §Source Code
  - Verify: the demo section, architecture line and concept note exist in the working repo
- [x] T028 Run the full suite and build for whoop-ui-service
  - Source: plan.md §Test Strategy (Full suite), SC-005
  - Verify: `cd whoop-ui-service && npm test && npm run typecheck && npm run build`
- [x] T029 Run quickstart.md validation end to end (steps 1–12, including cookies blocked and the real-user regression pass)
  - Source: plan.md §Delivery & Distribution, SC-001, SC-002, SC-003
  - Verify: follow `specs/001-demo-mode/quickstart.md` on a clean checkout; record pass/fail per step

> **Final gate** (run by `/sdd-build` before hand-off): every task above is checked or has an approved `DEFERRED:` note; full suite passes; every AS-x.y has passed at least once.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001 first; T002 any time.
- **Foundational (Phase 2)**: needs T001. T003 → T004; T005 → T006. BLOCKS all user stories.
- **US1 (Phase 3)**: needs Phase 2. Tests T007–T010 in parallel; then T011 → T012 → T013; T014 → T015 (T015 shares routes.test.ts results); T016 needs T006; T017 needs T016.
- **US2 (Phase 4)**: needs US1. Tests T018–T020 in parallel; then T021 → T022 → T023.
- **US3 (Phase 5)**: needs Phase 2 (T024, T025 can run after T021 for full coverage of write routes); T026 any time.
- **Review Findings (Phase R)**: no standalone tasks; covered above.
- **Polish (Phase N)**: after the stories you ship.

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Data and script before fakeApi; fakeApi before the component wiring
- Story complete (checkpoint passed) before moving to next priority

### Agent Execution Strategy

- The parent agent (`/sdd-build`) owns this file: only it ticks boxes and commits.
- `[P]` tasks in the same phase, with no unmet dependency and no shared files, go to parallel subagents (up to 4 at a time). Each subagent gets: its task block, the matching spec/plan excerpts, the constitution, and the files it may touch.
- Everything else runs sequentially in the parent.
- A task that fails its Verify 3 times stops the build: it gets a `BLOCKED:` note and `/investigate` takes over. Dependent tasks wait.

### Parallel Examples

- Phase 2: T003 ∥ T005 (different test files)
- US1: T007 ∥ T008 ∥ T009 ∥ T010; later T014 alongside T011–T013 (different files)
- US2: T018 ∥ T020 (T019 also extends fakeApi.test.ts, so it runs after T018)
- US3: T024 ∥ T025

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1 (a view-only demo: tabs populated, banner, leave/connect)
4. **STOP and VALIDATE** at the US1 checkpoint gate
5. Ship US1 (`/review` → `/qa` → `/ship`) if ready

### Incremental Delivery

1. Setup + Foundational → seam ready
2. US1 → checkpoint → ship (MVP: the dead end is gone)
3. US2 → checkpoint → ship (scripted AI replay)
4. US3 → checkpoint → ship (isolation proofs)

---

## Notes

- [P] tasks = different files, no dependencies
- One task per commit: `T012 [US1] <description>`
- Work found during build that isn't listed: add a task with `Source: BUILD` first, then do it
- No backend file changes in this feature (T026 checks it); no env vars, no migration
