# Quickstart: validating demo mode

How to prove the feature works end to end. Shapes are in [data-model.md](data-model.md),
routes in [contracts/demo-routes.md](contracts/demo-routes.md).

## Prerequisites

- `whoop-ui-service/.env` from `.env.example` (the backends don't need to run for the demo
  itself; they do for the real-user regression check).
- `cd whoop-ui-service && npm install`

## Automated checks

```bash
cd whoop-ui-service
npm test                 # Vitest: session parsing, sample data, scripts, /api guard
npm run typecheck
npm run build
```

Backends are untouched by this feature; their suites must still pass unchanged:

```bash
git diff --stat main -- whoop-service whoop-insight-service whoop-nutrition-service   # expect no output
```

## Manual walk-through (what `/qa` does in a browser)

1. Fresh private window → `http://localhost:3000/login` → click **Try the demo**. Expect the
   dashboard in one click, with the demo banner (AS-1.1, AS-1.5).
2. Visit Today, Fuel, Recovery, Sleep, Strain, Insights. Every tab shows data; Today shows
   today's date and numbers (AS-1.2, AS-1.3, AS-1.4).
3. Insights: switch daily/weekly/monthly, click **Generate insight** each time. Example text
   appears, no error (AS-2.1, AS-2.4).
4. Fuel: the example chat is pre-filled. Send a message, click a suggestion, click the mic,
   confirm and discard a meal, change the goal. No error, no mic permission prompt
   (AS-2.2, AS-2.4).
5. Click **Refresh**: spinner, then "just now" (AS-2.4).
6. Open DevTools → Network during steps 3–5: no request to `/api/*` or any backend (AS-2.3).
7. Reload: the demo is back to its original state (AS-2.5).
8. Second browser profile, start a demo, act in one; the other doesn't change (AS-3.1).
9. In the demo, `fetch('/api/whoop/recovery')` from the console → `401` (AS-3.2).
10. **Leave demo** → landing page; `/` now redirects to `/login` (AS-1.6).
11. Block cookies for localhost, click **Try the demo** → "the demo needs cookies" message.
12. Sign in as a real user: no banner, real data, Generate/chat/sync work as before (AS-3.3).
