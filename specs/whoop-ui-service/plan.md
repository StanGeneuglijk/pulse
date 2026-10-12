# Plan: whoop-ui-service

**Spec:** `spec.md` · **Constitution:** [`../constitution.md`](../constitution.md) (the principles that apply to a client)

## Summary

A Next.js (App Router) app. Server components render pages; thin `app/api/*` route handlers act as a backend-for-frontend, reading the session cookie and calling the three services through one small client module each. Client components (dashboard, insight panel, meal chat) only ever `fetch` those same-origin routes. Login is whoop-service's OAuth flow, finished by a server route that redeems the one-time code into the cookie.

## Technical context

| | |
|---|---|
| Framework | Next.js 14 (App Router), React 18, TypeScript |
| Styling / charts | Tailwind CSS, Recharts |
| State | None server-side beyond the session cookie |
| Voice | Browser `MediaRecorder` → multipart upload |
| Testing | `tsc --noEmit` and `next build` in CI |
| Deploy target | Render Node web service |

## Constitution check

| Principle | How this plan satisfies it |
|---|---|
| 2 (adapted) One boundary per backend | `lib/whoopClient.ts`, `lib/insightClient.ts`, `lib/nutritionClient.ts` are the only modules that add an `Authorization` header |
| 6 Explicit identity | each client function takes the `Session` as a parameter |
| 12 (adapted) Config in one place | `lib/config.ts` reads the three URLs, and nothing else reads `process.env` |
| 14 Distinct secrets | the app holds none; the per-user token is the user's own |
| 18 Scoped auth | the backends authorize every call against the token |

Deviations: none that apply.

## Project structure

```
whoop-ui-service/
├── app/
│   ├── login/page.tsx             # "Connect WHOOP" -> whoop-service /auth/login
│   ├── connected/route.ts         # redeem one-time code -> session cookie -> "/"
│   ├── page.tsx                   # dashboard (requires a session)
│   └── api/                       # backend-for-frontend routes
│       ├── whoop/{recovery,sleep,workout,syncs,sync}/route.ts
│       ├── insight/{generate,latest,list,usage}/route.ts
│       ├── nutrition/{chat,chat/audio,meals/confirm,meals/discard}/route.ts
│       ├── auth/logout/route.ts
│       └── health/route.ts
├── components/                    # Dashboard, RecoveryRing, RecoveryTrend, SyncButton,
│                                  # InsightPanel, NutritionPanel, StatusPill, LogoutButton
└── lib/
    ├── session.ts                 # cookie read/write; requireSession()
    ├── config.ts                  # the three backend URLs
    ├── whoopClient.ts insightClient.ts nutritionClient.ts
    ├── apiError.ts                # backend error -> status + message
    └── types.ts format.ts
```

## Key decisions

| Decision | Chosen | Rejected, and why |
|---|---|---|
| Where backend calls happen | Server route handlers (BFF) | Browser → backends directly — needs CORS and exposes the token to JS |
| Session storage | `httpOnly` cookie with `{userId, readToken}` | Server-side session store — the backends already validate the token on every call |
| Cookie signing | Unsigned | Signing adds no protection: tampering only breaks your own session |
| Identity | whoop-service's OAuth + one-time code | Own accounts/passwords — a second identity system for no gain |
| Voice upload | Through the app's own route | Browser → OpenAI — would need a vendor key in the browser |

## API surface (outline)

The app's own `/api/*` routes mirror the backend operations the UI uses, one handler each, all requiring a session except `/api/health`.

## Hosting

Render Node web service in the same region as the backends. Health-checked on `/login` (renders without any backend call), since `/api/health` waits on three free-tier backends that may be asleep. whoop-service's `FRONTEND_URL` must point at this app.

## What would change this design

- Many concurrent users with slow backends → add caching (`ETag` pass-through is already supported by whoop-service).
- A native app → the BFF routes become its API as-is.
