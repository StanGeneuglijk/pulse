# Feature Specification: Demo mode

**Feature Branch**: `001-demo-mode`

**Created**: 2026-10-08

**Status**: Draft

**Input**: User description: "Demo mode: let visitors without WHOOP explore the app with sample data (a GitHub issue in the working repo)."

**Design doc**: none (size M: no /office-hours session; the idea comes from a GitHub issue)

## Origin *(from the GitHub issue)*

**Problem**: The app only shows anything after you connect a WHOOP account. Most people who see the project (from a post, a portfolio, or a friend's link) don't own a WHOOP band. For them the live link is a dead end: they see the landing page and nothing else.

**Agreed premises**:

1. The audience is people evaluating the project, not WHOOP owners. Demo mode exists so they can see the whole product in under a minute.
2. No new data sources or integrations: the demo shows the same screens real users see, filled with sample data.
3. A demo visit must not cost money by default. AI output in the demo is pre-written example output, not a live model call.
4. Real users' data and experience are untouchable: the demo is a separate, sealed-off path.

## Clarifications

### Session 2026-10-08

- Q: When a demo visitor clicks something that would normally call AI or WHOOP (Generate insight, send a meal message, the mic, Refresh from WHOOP), what should happen? → A: Scripted replay. Buttons work but play pre-written results: Generate shows that period's example insight, the meal chat replays the example exchange, Refresh pretends to sync. Nothing is saved.
- Q: Should demo visitors ever get live AI, or only the pre-written examples? → A: None at all. The demo is entirely pre-written; live AI for visitors is out of scope (a possible later feature).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Explore the dashboard without WHOOP (Priority: P1)

A visitor opens the landing page from a link and has no WHOOP account. They click one clearly visible "Try the demo" button. They land straight in the dashboard as a sample person and can click through every tab: Today, Fuel, Recovery, Sleep, Strain and Insights. Each tab shows a believable month of data. A banner on every screen says this is a demo with sample data and offers a way to connect a real WHOOP account instead.

**Why this priority**: This is the whole point of the feature. Without it, nobody without a WHOOP band can see the product. It is a viable release on its own: even if the demo is view-only, the dead end is gone.

**Independent Test**: In a fresh browser with no session, open the landing page, click "Try the demo", and visit every tab. Every tab shows sample data, the demo banner stays visible, and no WHOOP login was needed.

**Acceptance Scenarios**:

1. **AS-1.1** — **Given** a visitor with no session on the landing page, **When** they click "Try the demo", **Then** they reach the dashboard within one click, with no sign-up, WHOOP connection or form.
2. **AS-1.2** — **Given** a visitor in the demo, **When** they open each of Today, Fuel, Recovery, Sleep, Strain and Insights, **Then** every tab shows sample data and none shows an empty state, error or loading spinner that never resolves.
3. **AS-1.3** — **Given** a visitor in the demo on any day, **When** they view the trend charts, **Then** the data covers at least the last 30 days up to and including today, so "Today" always shows today's numbers rather than a stale date.
4. **AS-1.4** — **Given** a visitor in the demo, **When** they view the Fuel tab, **Then** they see logged meals with calories and macros across multiple days, and a nutrition goal.
5. **AS-1.5** — **Given** a visitor in the demo, **When** they look at any screen, **Then** a visible label says it's a demo with sample data, and it offers a "Connect your WHOOP" action that starts the real connect flow.
6. **AS-1.6** — **Given** a visitor in the demo, **When** they choose to leave the demo, **Then** they return to the landing page with no demo session left behind.

---

### User Story 2 - See what the AI does, without paying for it (Priority: P2)

The AI features are the most interesting part of the product, so a visitor in the demo can see them. On the Insights tab they can read an example daily, weekly and monthly insight written about the sample person's data. On the Fuel tab they can see an example meal-chat exchange: a meal described in plain words, the assistant's proposed breakdown, and its confirmation. None of this triggers a paid AI call.

**Why this priority**: Without it the demo shows charts but hides the product's main idea. It depends on Story 1's demo session, but can be tested separately once a demo session exists.

**Independent Test**: Start a demo, open Insights and switch between daily, weekly and monthly; open Fuel and read the example chat. Check the AI providers' usage: it hasn't moved.

**Acceptance Scenarios**:

1. **AS-2.1** — **Given** a visitor in the demo, **When** they view Insights and pick daily, weekly or monthly, **Then** they see an example insight for that period that refers to the sample person's actual numbers.
2. **AS-2.2** — **Given** a visitor in the demo, **When** they open the Fuel tab's meal chat, **Then** they see an example exchange: a described meal, a proposed breakdown with items, calories and macros, and the confirmed result.
3. **AS-2.3** — **Given** any number of demo visits, **When** visitors use every demo screen and button, **Then** no paid AI call (insight, meal chat or voice transcription) is made on their behalf.
4. **AS-2.4** — **Given** a visitor in the demo, **When** they try an action that would normally call a paid AI service or WHOOP (generate an insight, send a chat message, record voice, refresh from WHOOP), **Then** the action plays a pre-written result (Generate insight shows that period's example insight, sending a meal message or using the mic replays the example meal-chat exchange, Refresh from WHOOP completes as a pretend sync), and the app never shows an error.
5. **AS-2.5** — **Given** a visitor in the demo who confirmed a meal, discarded one or changed the goal, **When** they reload the page, **Then** the demo is back to its original state: nothing they did was saved anywhere.

---

### User Story 3 - Many visitors at once, real users untouched (Priority: P3)

The link is shared publicly, so many strangers may use the demo at the same moment, and some will poke at it. One visitor's actions never show up for another, and no visitor can reach a real user's data by any means. Real users signed in with WHOOP notice no change at all.

**Why this priority**: This is a guardrail, not a visible feature. It matters as soon as the link is public, but Story 1 already delivers value without the extra hardening.

**Independent Test**: Run two demo sessions in two browsers side by side and act in one; the other is unchanged. In a demo session, try to request a real user's data directly; it is refused. Sign in as a real user; everything behaves as before.

**Acceptance Scenarios**:

1. **AS-3.1** — **Given** two visitors in the demo at the same time, **When** one of them takes any available action, **Then** what the other sees does not change.
2. **AS-3.2** — **Given** a visitor in the demo, **When** they try to reach any real user's data (for example by editing their session or calling the app's data endpoints with a real user's id), **Then** the request is refused and no real data is returned.
3. **AS-3.3** — **Given** a real user connected with WHOOP, **When** they use the app, **Then** they see no demo banner and no sample data, and every feature (sync, insights, meal chat, voice) behaves exactly as before.
4. **AS-3.4** — **Given** the batch sync runs, **When** it fans out to connected users, **Then** the sample person is not synced against WHOOP and causes no errors.
5. **AS-3.5** — **Given** the demo is used heavily, **When** the AI providers' spend is checked, **Then** demo use has not consumed any of the platform's AI spend cap or any real user's quota.

---

### Edge Cases

- A visitor already signed in as a real user opens the landing page: they go to their own dashboard as today. Starting a demo is not offered over a real session.
- A visitor in the demo clicks "Connect your WHOOP": the demo session ends and the real connect flow starts, so the two identities never mix.
- A visitor keeps a demo tab open past midnight, or returns days later: the sample data still reaches "today", and an expired demo session sends them back to the landing page instead of showing an error.
- A demo visitor's browser blocks cookies: they get a clear message that the demo needs cookies, not a blank page.
- The backends are cold-starting (free hosting plan sleeps): the demo shows the same loading states as real use and then resolves.
- Someone scripts thousands of demo starts: this creates no unbounded growth in stored data and costs no AI spend.

### Out of Scope

- New data sources or integrations of any kind.
- Live AI calls for demo visitors in any amount, capped or opt-in (a possible later feature).
- Accounts, sign-up, or saving a demo visitor's changes beyond their visit.
- Several sample personas, or letting visitors pick a profile.
- Analytics on demo usage.
- Rendering Markdown in insights and friendlier supplier error messages: separate issues, even though the demo shows those screens.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The landing page MUST offer a one-click "Try the demo" action alongside "Connect WHOOP", with no sign-up, form or WHOOP connection.
- **FR-002**: Starting the demo MUST put the visitor in the normal dashboard as a single, fixed sample person.
- **FR-003**: The sample person MUST have recovery, sleep, strain/cycle and workout data for at least the 30 days up to and including the current day, whenever the demo is opened.
- **FR-004**: The sample data MUST be realistic: plausible values and day-to-day variation, a visible story (for example a few hard training days followed by lower recovery), and no impossible values.
- **FR-005**: The sample person MUST have confirmed meals on most of those days and a nutrition goal, so the Fuel tab and the meal data in insights are populated.
- **FR-006**: The demo MUST show an example daily, weekly and monthly insight that refers to the sample person's data, and an example meal-chat exchange ending in a proposed and confirmed breakdown.
- **FR-007**: A demo visit MUST NOT trigger any paid AI call (insight, meal chat, transcription) or any call to WHOOP.
- **FR-008**: Actions that would normally call AI or WHOOP MUST play a pre-written result in the demo (scripted replay, AS-2.4) and MUST never surface as an error. Nothing a demo visitor does is saved anywhere (AS-2.5).
- **FR-009**: Every screen in the demo MUST carry a visible "demo, sample data" label with a "Connect your WHOOP" action, and a way to leave the demo.
- **FR-010**: Demo access MUST be scoped to the sample person only. It grants no access to any real user's data, and no operator-level capability.
- **FR-011**: One demo visitor's actions MUST NOT change what any other demo visitor sees. Because nothing in the demo is saved, the shared sample data is read-only for demo visitors.
- **FR-012**: The sample person MUST be excluded from WHOOP sync, from the platform's AI spend accounting, and from any real-user count.
- **FR-013**: Real users' experience MUST be unchanged: no banner, no sample data, no change to any existing feature's behavior.
- **FR-014**: Demo sessions MUST expire on their own (see Assumptions) and MUST NOT create stored data that grows with the number of visits.
- **FR-015**: Demo visitors MUST NOT get live AI in any form, not even a capped or opt-in allowance. All AI output in the demo is pre-written.

### Key Entities

- **Sample person**: the one fictional user every demo visitor sees. They have a name and profile, a month-plus of WHOOP-shaped data that always ends today, confirmed meals, a nutrition goal, and example insights. They are never a real WHOOP account and are never synced.
- **Demo session**: a visitor's time in the demo. It identifies the visitor as the sample person (and only that person), is clearly distinguishable from a real session, and expires on its own.
- **Example AI output**: pre-written insights (daily, weekly, monthly) and an example meal-chat exchange, written about the sample person's data and shown in place of live model output.

## Success Criteria *(mandatory)*

### Measurable Outcomes

| ID | Outcome | Verified by |
|----|---------|-------------|
| **SC-001** | A first-time visitor gets from the landing page to a populated dashboard in one click and under 10 seconds once the services are awake | `/qa` |
| **SC-002** | 6 of 6 tabs show sample data in the demo, with 0 errors or empty states | `/qa` |
| **SC-003** | 0 paid AI calls and 0 WHOOP calls caused by demo use, across a full QA run that clicks every demo control | `/qa`, plus provider usage checked in `/canary` |
| **SC-004** | 0 real-user records reachable from a demo session in the isolation checks (AS-3.2) | automated test + `/cso` |
| **SC-005** | Real-user flows pass unchanged: every existing test passes, and a signed-in real user sees no demo label | automated tests + `/qa` |
| **SC-006** | A stranger who has never used WHOOP can say what the product does after one demo visit | `/retro`, from feedback on the public post |

## Assumptions

- **One fixed sample person**, generated so the data always ends on the current day ("rolling" dates): a static snapshot would look abandoned within a week.
- **Example insights and the example chat are written once**, about the sample person's data, and kept with the sample data, so they never go stale relative to it.
- **A demo session lasts up to 24 hours** or until the visitor leaves the demo, whichever comes first. Nothing a demo visitor does is saved, even during the session: a reload resets the demo.
- **The demo label is a persistent banner**, not a dismissible popup, so screenshots of the demo always read as sample data.
- **The demo lives entirely in the dashboard app** (decided at planning, 2026-10-08): a demo session is a separate kind of session that carries no backend credential at all. The sample person exists only inside the dashboard app, never as a real user in the backends' database, so the backends never see demo traffic.
- **Hosting stays as it is**: the demo runs on the existing services and free-plan hosting, cold starts included. No new paid infrastructure.
- **Depends on** the dashboard app's existing rule that every data request needs a real signed-in session; a demo session is not one, so it can't reach any backend, and the backends' own per-user authorization (a credential for one person can never read another's data) stays the second line of defence.
