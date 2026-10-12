# Data model: Demo mode

Nothing in this feature is stored in a database. All three entities below live in
`whoop-ui-service`: one in a cookie, two as code. The demo reuses the existing wire types in
`whoop-ui-service/lib/types.ts` unchanged, so every tab renders demo data through the same
code paths as real data.

## Demo session (cookie value)

Carried in the existing `whoop_session` cookie (`httpOnly`, `sameSite=lax`, `secure` in
production), base64url JSON like the real session.

| Field | Type | Rule |
|-------|------|------|
| `kind` | `"demo"` | Present only on demo sessions. A value without `kind` is a real session (`{userId, readToken}`), unchanged. |
| `exp` | number (Unix ms) | Start time + 24 h. A demo value past `exp` reads as no session. |

- Holds **no** `userId` and **no** `readToken`. `requireSession()` never returns it, so no
  `app/api/*` route can build a backend request from it.
- Cookie `maxAge` = 24 h, matching `exp`.

**States**: none → demo (`GET /demo/start`, only when there is no real session) → none
(`POST /api/auth/logout`, `GET /demo/connect`, or expiry). A real login overwrites the
cookie, so demo → real is also possible; real → demo is not (`/demo/start` redirects a
real session to `/`).

## Sample person (code: `lib/demo/data.ts`)

| Part | Shape | Rules |
|------|-------|-------|
| Profile | `Profile` | Fixed fictional name, height, weight, max HR. |
| Day table | 35 rows, keyed by day offset (0 = today, −34 = oldest) | Each row: recovery score, HRV, RHR, SpO2, skin temp; main sleep (start/end, stages, efficiency, performance); cycle strain + kJ; 0–1 workout (sport, strain, HR, zones, kJ); 0–4 meals (description, local time, kcal, macros). |
| Goal | `NutritionGoal` | One active goal (for example `muscle_gain`, 2,600 kcal, 160 g protein). |

**Validation** (enforced by tests, FR-003/FR-004/FR-005):
- Recovery 1–99, HRV 20–150 ms, RHR 40–80 bpm, sleep 4–10 h with stages summing to time
  asleep, strain 0–21, kJ > 0, meal macros ≥ 0 and kcal ≈ 4·P + 4·C + 9·F (±15%).
- Offset 0 has recovery, a main sleep and a cycle (AS-1.3), and at least 30 consecutive
  days have recovery, sleep and cycle.
- Meals on at least 24 of the last 30 days (FR-005 "most days").
- Story: offsets −6…−4 strain ≥ 16, followed by recovery < 50 on at least one of −5…−3, and
  recovery ≥ 67 on offset 0.

## Generated dashboard data (code: `lib/demo/data.ts`)

`generateDemoData(now: Date): DashboardData`: maps each day-table row to the existing wire
types with local-calendar dates relative to `now` (R2). `fakeApi` calls it with `new Date()`
on every read (review D5); in-page changes (confirmed meals, goal edit) are kept as day
offsets and re-applied on top, and are lost on reload. Record ids are stable strings
(`demo-rec-<offset>`) so React keys stay stable. `syncs` holds one entry "a few minutes
ago" so the sync button shows a recent time.

## Fake API state (code: `lib/demo/fakeApi.ts`)

One instance per page load, in memory only. Holds confirmed meals (as day offset + time +
proposal) and an optional goal override. Two tabs or two browsers each have their own
instance (AS-3.1); a reload creates a fresh one (AS-2.5). Unknown paths throw.

## Example AI output (code: `lib/demo/script.ts`)

| Item | Shape | Rules |
|------|-------|-------|
| Insights | `Record<InsightPeriod, {content, ...}>` → `InsightRecord` built with period dates from `now` | One each for daily, weekly, monthly. Every number quoted in the text matches the day table (test, AS-2.1). `modelName` shows as "example (demo)". |
| Meal chat | `{ userText, reply, proposal: MealProposal }` | One example meal; proposal totals equal the sum of its items. The pre-filled exchange ends with the "Logged ✓" line (AS-2.2). |
| Sync | delay in ms | Pretend sync duration for the Refresh button. |
