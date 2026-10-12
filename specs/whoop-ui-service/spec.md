# Spec: whoop-ui-service

**Status:** built
**Depends on:** whoop-service, whoop-insight-service, whoop-nutrition-service

## Summary

A web dashboard where anyone with a WHOOP account can connect it, see their recovery, sleep and strain, refresh from WHOOP, ask for an AI insight, and log meals by typing or speaking. It is purely a client of the three backends: no database, no business logic, and no operator keys — every call is made as the logged-in person.

## User stories

### US1 — Log in with WHOOP (P1)

As a visitor, I want to connect my WHOOP account and stay logged in, so that I see my own data.

**Independent test:** with whoop-service running, complete login; the dashboard loads with a session cookie the browser's JavaScript can't read.

**Acceptance scenarios**

1. **Given** I'm not logged in, **when** I open the app, **then** I'm sent to a login page with a "Connect WHOOP" action.
2. **Given** I connect, **when** WHOOP sends me back, **then** the app redeems the one-time code server-side, stores my session in an `httpOnly` cookie, and shows the dashboard.
3. **Given** the one-time code is expired or reused, **when** I land back, **then** I see a clear "try connecting again" message.
4. **Given** I log out, **when** I reload, **then** I'm on the login page.

### US2 — See my data (P1)

As a logged-in user, I want today's recovery, recent sleep and strain, and a trend, so that I get the picture at a glance.

**Acceptance scenarios**

1. **Given** synced data, **when** the dashboard loads, **then** I see my latest recovery, sleep and strain and a recent trend.
2. **Given** no data yet (first sync still running), **when** the dashboard loads, **then** I see an empty state, not an error.
3. **Given** I press "Refresh from WHOOP", **when** the sync is queued, **then** I see it's syncing, and the last-sync status updates.

### US3 — Get an insight (P2)

As a user, I want to generate a daily, weekly or monthly insight, so that I understand my numbers.

**Acceptance scenarios**

1. **Given** I pick a period and press generate, **when** it completes, **then** the insight is shown.
2. **Given** the backend refuses (no data, over budget, already running), **when** I press generate, **then** I see the backend's reason in plain words.

### US4 — Log a meal (P2)

As a user, I want a chat panel where I type or record a meal and confirm the estimate, so that logging takes seconds.

**Acceptance scenarios**

1. **Given** I type a meal, **when** the assistant proposes a breakdown, **then** I see items and totals with Confirm and Discard.
2. **Given** I press the mic button and speak, **when** I press it again to stop, **then** the recording is sent, and I see the transcript and the assistant's reply.
3. **Given** my browser denies microphone access, **when** I press the mic, **then** I see why and can still type.

## Functional requirements

- **FR-001** The browser only calls this app's own same-origin `/api/*` routes; those call the backends server-side.
- **FR-002** The user's `read_token` lives only in an `httpOnly`, `secure` (in production), `sameSite=lax` cookie — never in a response body or client JS.
- **FR-003** Every backend call carries the session's `read_token`; the app holds no API keys.
- **FR-004** Backend errors are passed through as a status and a readable message.
- **FR-005** Voice is recorded in the browser (`MediaRecorder`) and uploaded through the app's server route.
- **FR-006** Configuration is only the three backend base URLs.

## Key entities

- **Session** — `{userId, readToken}` in a cookie; the backends re-validate it on every call.

## Success criteria

- **SC-001** No secret is ever present in client-side JavaScript or a URL.
- **SC-002** A tampered cookie can at most break that user's own session.
- **SC-003** The app builds and typechecks in CI with only the three URLs configured.

## Out of scope

- Its own user accounts or passwords — identity is WHOOP via whoop-service.
- Editing goals or past meals in the UI (the API supports goals; UI can follow).
- Offline support, push notifications, a native app.
