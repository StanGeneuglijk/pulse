# Spec: whoop-nutrition-service

**Status:** built
**Depends on:** whoop-service (`read_token`), an LLM provider (chat), a speech-to-text provider (optional)

## Summary

Let a connected user log meals by describing them in conversation — typed or spoken — and get an estimated nutritional breakdown they confirm before it's saved. Let them set a goal (e.g. weight loss) that the assistant keeps in mind, and see totals against it. Confirmed meals become an input to whoop-insight-service.

## User stories

### US1 — Log a meal by describing it (P1)

As a user, I want to tell the assistant what I ate in plain words, so that I don't have to look up calories myself.

**Independent test:** with a fake LLM, send "two eggs and toast"; a proposed breakdown comes back and nothing is saved.

**Acceptance scenarios**

1. **Given** I describe a meal in enough detail, **when** I send it, **then** I get a structured proposal: items with quantity, calories, protein, carbs and fat, plus totals and when I ate it.
2. **Given** my description is ambiguous ("a burrito"), **when** I send it, **then** the assistant asks one clarifying question instead of guessing.
3. **Given** I say "this morning" or "yesterday", **when** a proposal is made, **then** its time resolves against today's date.
4. **Given** a conversation, **when** I send more messages, **then** the assistant sees the recent history, not just the last message.

### US2 — Nothing is saved until I confirm (P1)

As a user, I want to review the estimate and confirm or discard it, so that my log only contains numbers I accepted.

**Acceptance scenarios**

1. **Given** a pending proposal, **when** I confirm, **then** a meal with its items is saved and the proposal is cleared.
2. **Given** a pending proposal, **when** I discard, **then** nothing is saved and the proposal is cleared.
3. **Given** nothing is pending, **when** I confirm or discard, **then** I get `409` — never a silent no-op.
4. **Given** someone else's conversation, **when** I try to confirm it, **then** I get `401`, and an unknown credential can't learn whether that conversation exists.

### US3 — Speak instead of typing (P2)

As a user on my phone, I want to record a voice message, so that logging a meal is quick.

**Acceptance scenarios**

1. **Given** a voice recording, **when** I send it, **then** it's transcribed and handled exactly like a typed message, and I see the transcript.
2. **Given** voice isn't configured on this deployment, **when** I send audio, **then** I get `503`; text chat still works.
3. **Given** an upload over the size limit, **when** I send it, **then** I get `413` before any provider is called.

### US4 — Goals and summaries (P2)

As a user trying to lose weight, I want to set a goal and see my intake against it, so that the assistant's guidance and my totals reflect what I'm aiming for.

**Acceptance scenarios**

1. **Given** I set a goal, **when** I set a new one, **then** only the new one is active.
2. **Given** an active goal, **when** I chat, **then** the assistant may reference progress toward it.
3. **Given** confirmed meals, **when** I ask for a weekly summary, **then** I get totals, average calories per day and the difference from my goal.

### US5 — Bounded cost (P1)

As the operator, I want chat and transcription spending capped per user and in total, so that cost is predictable.

**Acceptance scenarios**

1. **Given** my estimated spend reached the per-user cap, **when** I send text or audio, **then** I get `402` before any provider call.
2. **Given** a turn in progress in a conversation, **when** a second message arrives for it, **then** it gets `409`.

## Functional requirements

- **FR-001** Each chat turn sends a bounded recent history and a system prompt (behavior rules, today's date, active goal) to the LLM with one tool for proposing a meal breakdown; the model decides whether to call it.
- **FR-002** Proposals are validated (schema, timestamp) at the provider boundary and staged on the conversation, never saved directly.
- **FR-003** Confirm writes the meal and its items in one transaction; discard clears the proposal.
- **FR-004** Voice: transcribe, then run the same turn with the transcript; transcription is optional per deployment.
- **FR-005** Chat and transcription are separate provider interfaces with separate credentials.
- **FR-006** Spend is estimated from tokens (chat) and audio seconds (transcription); caps are checked before each paid call.
- **FR-007** Per-user routes accept the operator key or the user's `read_token`; conversation routes check ownership.
- **FR-008** Inputs are bounded: message length, audio size, query ranges.

## Key entities

- **Conversation** — a user's chat thread; holds at most one pending proposal.
- **Message** — one user or assistant turn.
- **Meal (nutrition log)** and **meal item** — a confirmed meal and its parts; a new record each time (not deduplicated).
- **Goal** — a user's target; one active per user.
- **Job log** — one chat or transcription attempt with its usage.

## Success criteria

- **SC-001** No LLM estimate becomes a saved meal without an explicit confirm.
- **SC-002** A conversation's cost per turn stays flat as it grows (bounded context).
- **SC-003** The service starts and serves text chat without a speech-to-text key.
- **SC-004** The full test suite runs without network access or spend.

## Out of scope

- A nutrition database lookup — estimates are the LLM's; the confirm step is the safeguard.
- Photo-based logging.
- Meal plans or recipes.
- Editing a confirmed meal (discard and re-log instead).
