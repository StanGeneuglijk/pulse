# Contract: demo routes and session (whoop-ui-service)

The demo adds two browser-facing routes and one rule for every existing `app/api/*` route.
Nothing changes in whoop-service, whoop-insight-service or whoop-nutrition-service.

## `GET /demo/start`

| Caller state | Response |
|--------------|----------|
| Real session | `307` → `/` (a demo is never started over a real session) |
| Demo session or none | Sets `whoop_session` to a fresh demo value (24 h), `307` → `/?demo=started` |

Makes no backend call.

## `GET /demo/connect`

Clears `whoop_session`, `307` → `${WHOOP_SERVICE_URL}/auth/login` (the real connect flow).
Makes no backend call itself.

## `POST /api/auth/logout` (existing, unchanged)

Clears `whoop_session` for real and demo sessions alike. "Leave demo" uses it.

## Pages

| Route | Real session | Demo session | None |
|-------|--------------|--------------|------|
| `/` | Dashboard, as today | Dashboard in demo mode (banner, sample data, scripted replay) | `307` → `/login`; with `?demo=started` → `/login?error=cookies_blocked` |
| `/login` | `307` → `/` | `307` → `/` | Landing page with "Connect WHOOP" and "Try the demo" |

## Rule for every existing `app/api/*` data route

A request with a demo session (or none) gets `401 {"error": "Not authenticated"}` and makes
**no** outbound request. This already follows from `requireSession()` returning only real
sessions; `tests/demo/api-guard.test.ts` proves it for every route file except
`app/api/health` (no session, no user data) and `app/api/auth/logout`.

The demo dashboard never calls these routes (R4); the rule is the server-side guard if a
visitor calls them by hand (AS-3.2).
