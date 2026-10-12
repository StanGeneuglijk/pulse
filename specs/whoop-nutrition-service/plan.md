# Plan: whoop-nutrition-service

**Spec:** `spec.md` · **Constitution:** [`../constitution.md`](../constitution.md) · **AI reasoning:** `whoop-nutrition-service/LEARNINGS.md`

## Summary

An async FastAPI service with the same shape and copied `core/` as whoop-insight-service. A chat turn runs inline: cap check, per-conversation lock, bounded history + goal-aware system prompt, one Claude call with a `propose_meal_breakdown` tool, then either a reply or a staged proposal. Confirm/discard is a small state machine on the conversation. Voice is a second provider seam (OpenAI transcription) in front of the same turn.

## Technical context

| | |
|---|---|
| Language / framework | Python 3.12, FastAPI, async SQLAlchemy + asyncpg |
| LLM | Anthropic Messages API with tool use, behind `ChatLLMClient` |
| Speech-to-text | OpenAI transcription (`whisper-1`), behind `TranscriptionClient`, optional |
| Storage | The shared Postgres; own `nutrition_*` tables; own Alembic version table |
| Locking | Redis `SET NX` per conversation |
| Testing | pytest with fake chat and transcription clients |
| Deploy target | One Render web service |

## Constitution check

| Principle | How this plan satisfies it |
|---|---|
| 1, 3 Layering | `core/` product-agnostic; `api/main.py` only aggregates |
| 2 (adapted) External boundaries | one module per vendor SDK (`providers/`) |
| 5 Async I/O | async DB, Redis and SDK clients |
| 6 Explicit `user_id` | every function takes it |
| 9 Fail fast | pending-meal, lock, cap, provider and transcription errors are domain exceptions |
| 12–14 Config/secrets | own `API_KEY`; separate Anthropic and OpenAI keys |
| 18 Scoped auth | by `user_id`, or by conversation ownership |

Deviations: **C-VII (every write is an upsert)** doesn't hold for meals — eating the same meal twice is two events, so `nutrition_logs` is a plain insert, created only by an explicit confirm. Conversations, messages and logs are append-only for the same reason.

## Project structure

```
whoop-nutrition-service/
├── api/main.py
├── core/                          # same trimmed core/ as insight
├── services/nutrition/
│   ├── router.py                  # chat, chat/audio, confirm/discard, meals, goals, usage
│   ├── chat.py                    # orchestration of one turn
│   ├── llm.py                     # ChatLLMClient protocol, tool schema, MealProposal
│   ├── transcription.py           # TranscriptionClient protocol
│   ├── providers/                 # anthropic_client.py, openai_whisper_client.py, factories
│   ├── prompt.py                  # system prompt: rules, today's date, goal
│   ├── config.py pricing.py       # models, caps, bounds; $/token and $/minute
│   └── auth.py lock.py crud.py models.py schemas.py exceptions.py activity_log.py
├── alembic/                       # version_table = nutrition_alembic_version
├── scripts/run_chat_example.py
└── tests/
```

## Key decisions

| Decision | Chosen | Rejected, and why |
|---|---|---|
| Getting structured macros | Tool use with a strict schema, `tool_choice: auto` | Parsing JSON from free text — brittle; forcing the tool — guesses instead of asking |
| Accuracy | LLM estimate + human confirm | Nutrition database lookup — big integration, out of scope |
| Saving | Stage on the conversation, save on confirm | Save immediately — unreviewed estimates in the log |
| Context | Last 20 messages | Full history — cost grows with every turn |
| Voice | Separate `TranscriptionClient` | A branch in the chat client — different vendor, secret and billing unit |
| Voice optional | Resolve the transcription client per request | Required at startup — blocks text-only deployments |
| Meal writes | Plain insert | Upsert — a repeated meal is a real second event |

## Data model (outline)

- `nutrition_conversations` — user_id, `pending_meal` (JSON, nullable).
- `nutrition_messages` — conversation → role, content.
- `nutrition_logs` + `nutrition_meal_items` — confirmed meal with totals and provenance (model); items per meal.
- `nutrition_goals` — goal type, optional targets, notes, `is_active` (one per user).
- `nutrition_job_logs` — status, model, tokens or audio seconds, duration, error.
- `nutrition_activity_logs` — route hits.

## API surface (outline)

| Route | Auth | Purpose |
|---|---|---|
| `POST /nutrition/chat/{id}` | user | One text turn |
| `POST /nutrition/chat/{id}/audio` | user | Transcribe, then one turn |
| `POST /nutrition/meals/confirm/{conversation}` · `discard/{conversation}` | owner | Resolve the pending proposal |
| `GET /nutrition/meals/{id}` · `/summary?period=` | user | Meals; totals vs. goal |
| `GET` · `PUT /nutrition/goals/{id}` | user | Active goal |
| `GET /nutrition/{id}/usage` · `/activity` · `GET /nutrition/spend` | user · operator | Usage and spend |

## Hosting

One Render web service in the database's region, sharing Supabase and Upstash. RLS (no policies) on every table. whoop-insight-service reads `nutrition_logs` and `nutrition_goals` directly — a schema change here must be checked against its `nutrition_read.py`.

## What would change this design

- Estimates need to be accurate, not approximate → add a nutrition-database lookup as a second tool.
- Photo logging → a vision-capable model call as another input path to the same turn.
- Long voice notes → stream transcription, or move it to a background job.
