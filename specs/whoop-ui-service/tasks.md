# Tasks: whoop-ui-service

`[P]` = can run in parallel with the tasks next to it · `[USn]` = the user story a task serves.
Every task ends with `npm run typecheck` and `npm run build` green.

## Phase 1 — Setup

- [x] T001 Next.js App Router project with TypeScript and Tailwind; `.env.example` with the three backend URLs.
- [x] T002 `lib/config.ts` — required env vars, read once, server-only.

**Checkpoint:** `npm run dev` serves an empty page.

## Phase 2 — Foundation (blocks every story)

- [x] T003 `lib/session.ts` — read/write/clear the `httpOnly` cookie; `requireSession()`.
- [x] T004 `lib/apiError.ts` — `handleRoute()` mapping backend errors and missing sessions to status + message.
- [x] T005 [P] `lib/whoopClient.ts`, `lib/insightClient.ts`, `lib/nutritionClient.ts` — typed calls taking a `Session`.
- [x] T006 [P] `lib/types.ts` — response types matching the backends' camelCase JSON.

**Checkpoint:** a route handler can call a backend as a given session.

## Phase 3 — US1 Log in with WHOOP (P1, MVP)

- [x] T007 [US1] `app/login/page.tsx` — link to whoop-service `/auth/login`; error messages from `?error=`.
- [x] T008 [US1] `app/connected/route.ts` — redeem the code, set the cookie, redirect to `/`.
- [x] T009 [US1] `app/page.tsx` redirects to `/login` without a session; `api/auth/logout` clears it.

**Checkpoint:** US1 scenarios pass against a running whoop-service.

## Phase 4 — US2 See my data (P1)

- [x] T010 [US2] `api/whoop/*` routes (recovery, sleep, workout, syncs, sync).
- [x] T011 [US2] `Dashboard`, `RecoveryRing`, `RecoveryTrend`, `StatusPill`; empty states.
- [x] T012 [US2] `SyncButton` — queue a sync, show syncing, refresh the last-sync status.

**Checkpoint:** US2 scenarios pass.

## Phase 5 — US3 Get an insight (P2)

- [x] T013 [US3] `api/insight/*` routes; `InsightPanel` with a period picker and the backend's error message on failure.

## Phase 6 — US4 Log a meal (P2)

- [x] T014 [US4] `api/nutrition/chat` and `chat/audio` (multipart pass-through); confirm/discard routes.
- [x] T015 [US4] `NutritionPanel` — chat thread, proposal card with Confirm/Discard, mic via `MediaRecorder`, permission errors.

**Checkpoint:** a meal typed or spoken is confirmed and appears in the backend.

## Phase 7 — Polish and ship

- [x] T016 `api/health` fanning out to the three backends; `render.yaml` health-checked on `/login`.
- [x] T017 CI job: typecheck and build.

**Checkpoint:** deployed; the full flow works in a browser.
