# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Source of truth

The full build spec is [`claude_duolingo_assessment_prompt (1).md`](<claude_duolingo_assessment_prompt (1).md>) (Scaler AI Labs · SDE Fullstack Assessment). **When this file and the spec disagree, the spec wins. Explicit instructions from the user override both.** Section references below (§N) point into that spec. Re-read the relevant section before implementing a feature. Don't work from memory.

**Goal:** a gamified language-learning web app (Spanish, French, Punjabi, English) with an original mascot ("Pico") and original icons. Don't clone repos or copy proprietary code or assets (no Duolingo owl, logos or artwork).

## User overrides (explicit instructions that supersede the spec)

- **Branding is "Duolingo".** The user asked for this despite spec §0 (original name). The name lives in one constant each: `frontend/lib/brand.ts` (`APP_NAME`) and `backend/app/config.py` (`APP_NAME`). The mascot, icons and artwork stay original.
- **Multiple courses:** Spanish (the spec's demo course), French, Punjabi (Gurmukhi, romanized input accepted) and English (monolingual beginner course). Content lives in `backend/app/content/<lang>.py`, registered in `backend/app/content/__init__.py`, and every course must pass `content/builders.validate_course`.
- **Nothing is "Coming soon".** Settings (profile, theme, learning language, notifications, sound, account reset/restore) all work and persist, and the out-of-hearts modal's Practice button starts real heart practice (`/practice`, `POST /api/practice/start`: mistakes are free, finishing restores one heart, no XP).
- **Dark mode:** Light/Dark/System, stored per device, applied as `data-theme` on `<html>` before paint. Use theme tokens (`bg-card`, `bg-surface`, `text-ink`, `text-muted`, `*-light` backgrounds with `text-*-ink`), never `bg-white` for themed surfaces.

## How to work

- **Build, don't describe.** Act autonomously. Ask only when genuinely blocked. Record notable decisions (with the alternatives considered) in `INTERVIEW_NOTES.md → Decisions`.
- **Verify, never assume.** Never say "this should work". Run the server, hit the endpoints, run `pytest`, run `npm run build`, read the errors, fix them.
- **Keep it runnable after every phase.** Commit at each phase exit with the message `phase-N: <name>` (e.g. `phase-2: backend foundation`). The repo is **not yet a git repo**, so run `git init` in Phase 1.
- **Do phases in order** (§11). Never start Phase 7 polish while any P0 item is broken.
- **Priority tiers.** If time runs short, cut from the bottom, never from P0:
  - **P0:** backend + frontend start · SQLite + seed · learning path · lesson player · all 5 exercise types · feedback bar · hearts · lesson completion · server-side XP · persistence across refresh
  - **P1:** streak · daily goal · skill progress + unlocking · profile · leaderboard · backend tests · README
  - **P2:** achievements · settings · heart refill · animations · INTERVIEW_NOTES depth · extra polish
- **Dependencies:** every dependency must be justifiable in one sentence.
- **Never add:** auth systems, payments, social features, microservices, Redux/Zustand, ORMs other than SQLAlchemy, or component libraries that fight Tailwind.

## Subagents

The user has authorized the project subagents in [.claude/agents/](.claude/agents/). Use them at the checkpoints below, and only when the work actually exists. The main session does all building. Agents review, verify or document, so no two agents ever edit the same files.

| Agent | Can edit? | Use when |
|---|---|---|
| `spanish-content-reviewer` | no (read-only) | After `backend/app/seed.py` or any exercise content is written or changed, and before the Phase 2 commit |
| `game-rules-auditor` | no (read-only) | End of Phase 2, before the Phase 3 commit, before Phase 8, and after any change to attempt, answer, hearts, streak, XP or unlock logic |
| `verifier` | no (runs commands only) | Before **every** phase-exit commit, and whenever the project's health is in doubt |
| `docs-writer` | README, INTERVIEW_NOTES and `.env.example` only | Phase 9, or when docs drift after significant code changes |

Rules for using them:
- **Run independent agents in parallel** (e.g. `spanish-content-reviewer` + `game-rules-auditor` at the end of Phase 2). Wait for their reports, then fix the findings in the main session.
- **Commit gate:** commit a phase only after `verifier` reports `ALL GREEN`, or after the remaining failures have been consciously deferred and recorded in the phase tracker.
- **Agents never commit.** Only the main session runs `git commit`.
- **Relay findings:** the user doesn't see agent reports, so summarize what matters to them.
- **Don't delegate small tasks.** Don't spawn an agent for something a single Grep or command answers. The codebase is small enough to explore directly, so skip the built-in Explore agent.
- **Browser journey (§9.4):** the main session runs it with the `playwright-skill` skill, not through an agent.
- **Loading:** agent definitions load at session start, so start a new session after editing them. The `/agents` wizard no longer exists; edit the files directly.
- **Fallback:** if an agent isn't listed as available in the current session, the main session runs its checklist itself and says so.

## Phase tracker

Update this list as phases complete.

- [x] 1 · Inspect: workspace, tooling, plan (≤10 lines)
- [x] 2 · Backend: config, models, seed, services, all endpoints. Exit: seed runs, `/docs` works, smoke test passes
- [x] 3 · Tests: pytest suite from §9.1. Exit: `pytest` green
- [x] 4 · Path: layout, nav, stats bar, learning path, popover. Exit: home renders live data showing all 4 skill states
- [x] 5 · Lesson: player, 5 exercise types, feedback, completion, out-of-hearts. Exit: full lesson playable end to end
- [x] 6 · Secondary: profile, leaderboard, achievements, settings. Exit: all routes render
- [x] 7 · Polish: animations, responsive pass, loading/error/empty states. Exit: `npm run build` passes
- [x] 8 · Verify: §9.2–9.4, fix everything found. Exit: journey passes after a hard refresh
- [x] 9 · Docs: README, INTERVIEW_NOTES, `.env.example` files. Exit: setup commands re-run from scratch successfully

## Environment (this machine)

- Windows 11. Primary shell is PowerShell; Git Bash is also available.
- Node 22.20.0 · npm 11.7.0 · git 2.51.0
- **Python 3.14.0 is the only interpreter installed** (the spec requires 3.11+, so it qualifies). Pin backend dependency versions that ship Python 3.14 wheels, especially `pydantic`/`pydantic-core`. Confirm with a real `pip install -r requirements.txt` in a fresh venv before committing the pins.
- **Python environment:** the project venv is named **`duolingo`** and lives at the repo root (`./duolingo/`). It was created with `python -m venv duolingo`. Always install into and run from it. Never use the global interpreter, and don't create other venvs. Conda is not installed.
- **Frontend is React:** it's written in React through Next.js (App Router), as the spec requires. Don't switch to Vite or CRA unless the user asks.

## Commands

These are the target commands. Keep them exactly in sync with the README once they exist, and verify each one by running it.

```powershell
# Python env (from repo root) — venv named "duolingo"
python -m venv duolingo               # only if ./duolingo doesn't exist yet
.\duolingo\Scripts\Activate.ps1       # macOS/Linux: source duolingo/bin/activate

# Backend (from backend/, with the duolingo env active)
pip install -r requirements.txt
python -m app.seed --reset            # idempotent; creates/overwrites backend/app.db
uvicorn app.main:app --reload --port 8000   # Swagger UI at http://localhost:8000/docs
pytest                                # full suite
pytest tests/test_gamification.py -k streak   # single file / filtered tests
python scripts/smoke_test.py          # needs the server running on a freshly seeded DB

# Frontend (from frontend/)
npm install
npm run dev                           # http://localhost:3000
npx tsc --noEmit
npm run lint
npm run build                         # MUST pass; dev mode hides errors
```

Default ports: backend `8000`, frontend `3000`. The frontend reads `NEXT_PUBLIC_API_URL` (e.g. `http://localhost:8000`). Backend CORS allows only the frontend origin.

## Architecture

```text
frontend/ (React via Next.js App Router, TS strict, Tailwind, next/font)
   │  REST/JSON via lib/api.ts
   ▼
backend/app/routers/   (thin: parse, call service, return schema)
   ▼
backend/app/services/  (ALL game rules; pure-ish, take now/today as params)
   ▼
SQLAlchemy 2.x models → SQLite (backend/app.db)
```

Backend layout (§6):

```text
backend/app/
├── main.py            # app, CORS, router registration, exception handlers
├── config.py          # constants + env overrides
├── database.py        # engine, SessionLocal, Base, get_db
├── deps.py            # get_current_user() → the seeded learner (the single auth seam)
├── models.py
├── schemas.py         # Pydantic v2
├── seed.py            # python -m app.seed [--reset]
├── routers/           # course.py, lessons.py, me.py, social.py
└── services/          # answer_check.py, lesson_service.py, progress_service.py, gamification.py
backend/tests/         # conftest.py (in-memory SQLite fixture), test_*.py
backend/scripts/smoke_test.py
```

Frontend components (§8.3):

```text
components/lesson/
  LessonPlayer.tsx  ExerciseRenderer.tsx  FeedbackBar.tsx  LessonComplete.tsx  OutOfHeartsModal.tsx
  exercises/ MultipleChoice.tsx  WordBank.tsx  MatchPairs.tsx  FillBlank.tsx  TypeAnswer.tsx
lib/api.ts    # typed fetch wrapper; parses the error format; throws typed errors
lib/types.ts  # mirrors the Pydantic schemas
```

Routes: `/` (path plus a right rail with streak, daily goal and hearts) · `/lesson/[id]` (full screen, no nav) · `/profile` · `/leaderboard` · `/settings` (all settings work) · `/practice` (heart practice, full screen). Desktop (≥1024px) gets a left sidebar; mobile gets a bottom tab bar.

## Non-negotiable rules

### The backend is the single source of truth

- The client **never** sends or computes XP, hearts, streak, progress, unlocks or achievements. Client state is limited to: current selection, current index, feedback, word-bank tiles and matched cards.
- `solution` **never** leaves the server. The one exception is `MATCH_PAIRS`, whose pairs sit in `payload`; it validates on the client and a mismatch **costs no heart**. Document this trade-off in INTERVIEW_NOTES.
- Game constants live in `config.py` and can be overridden by env vars: `MAX_HEARTS=5`, `HEART_REGEN_MINUTES=30` (set to `1` in `.env` for demos), `HEART_REFILL_GEM_COST=350`, `BASE_LESSON_XP=10`, `PERFECT_BONUS_XP=5`, `PRACTICE_XP=5` (`0` disables it), `DEFAULT_DAILY_GOAL_XP=20`, `APP_TIMEZONE=Asia/Kolkata`.
- Rule functions take `now`/`today` **as parameters**. They never call `datetime.now()` or `date.today()` internally. "Today" means the date in `APP_TIMEZONE`, computed in one helper.
- Every user-scoped query gets its user from `Depends(get_current_user)`. Never hard-code the user ID anywhere else.

### Lesson attempts (§3.2)

1. `POST /api/lessons/{id}/start` creates an `IN_PROGRESS` attempt and returns exercises **without solutions**. Errors: `403 LESSON_LOCKED`, `409 OUT_OF_HEARTS` (apply heart regen before checking).
2. `POST /api/attempts/{id}/answer` validates the answer server-side.
   - Wrong: `mistakes += 1` and hearts `-= 1`, floored at 0, with regen applied first.
   - Storage is unique on `(attempt_id, exercise_id)`. A repeat submission returns the **stored** result and deducts **no** heart.
   - When hearts hit 0 the attempt becomes `FAILED` and the response includes `out_of_hearts: true`.
3. `POST /api/attempts/{id}/complete` requires every exercise to be answered and the status to be `IN_PROGRESS`.
   - First completion of a lesson earns `BASE_LESSON_XP` + (`PERFECT_BONUS_XP` if `mistakes == 0`). A replay earns `PRACTICE_XP` only.
   - If the attempt is already `COMPLETED`, return the stored summary with `already_completed: true` and award nothing.
   - XP, daily activity, streak, lesson/skill progress, unlocks and achievements all update in **one transaction**.

### Hearts (§3.3)

- Store `hearts` and `hearts_updated_at`. Regeneration is **lazy**, with no background jobs: effective hearts = `min(MAX, stored + floor(elapsed / interval))`, applied on every read and before any deduction.
- When regenerating, advance `hearts_updated_at` by the *consumed* intervals only, so partial progress toward the next heart is kept. At full hearts, reset the clock on the next deduction, and return `next_heart_at: null`.
- `POST /api/me/hearts/refill` spends 350 gems and sets hearts to full, or returns `400 INSUFFICIENT_GEMS`. Gems are seeded at 500 and are never earned.

### Streak (§3.4) — updated only on lesson completion

```text
last == today      → unchanged
last == today - 1  → streak += 1
otherwise          → streak = 1
longest_streak = max(longest_streak, streak)
```

On read, if `last_activity_date < today - 1`, **display** the streak as 0 (no cron job needed).

### Daily goal (§3.5)

`daily_activity` is unique on `(user_id, date)` and accumulates `xp_earned` and `lessons_completed`. The goal is met when today's `xp_earned >= user.daily_goal_xp`. `just_met` is true only on the crossing, `before < goal <= after`, so it fires exactly once.

### Skills and unlocking (§3.6)

- Skills have a **course-wide** `order_index`. The first skill starts unlocked; the next one unlocks when the previous skill is `COMPLETED`. Lessons within a skill unlock sequentially.
- The backend derives skill state: `LOCKED` (not unlocked) · `AVAILABLE` (0 lessons done) · `IN_PROGRESS` (0 < done < total) · `COMPLETED` (done == total). Progress % = done / total. Replays never double-count.

### Achievements (§3.7)

Checked inside the completion transaction. Each unlocks at most once, enforced by `unique(user_id, achievement_id)`, and is returned in `new_achievements`:
`FIRST_LESSON` 🏆 First Steps · `PERFECT_LESSON` 🎯 Flawless · `XP_100` ⭐ XP Hunter · `STREAK_3` 🔥 On Fire · `LESSONS_5` 📚 Dedicated (5 *distinct* lessons).

### Answer checking (§5)

- `normalize()` is a shared helper and must be unit-tested: lowercase → trim → collapse whitespace → strip `.,!?¿¡`.
- For `TYPE_ANSWER` and `WORD_BANK`, an answer that matches **only after removing accents** is correct and gets `note: "Watch your accents: <correct answer>"`.
- Support multiple accepted answers (e.g. `buenos días` / `buen día`).
- The answer response shape is fixed: `{ correct, correct_answer, explanation, note, hearts, out_of_hearts }`.

| type | payload (to client) | solution (server only) | client submits |
|---|---|---|---|
| `MULTIPLE_CHOICE` | `{options}` | `{answer}` | `{answer}` |
| `WORD_BANK` | `{tiles}` (shuffled, 1–3 distractors) | `{accepted}` | `{tiles}` in order |
| `MATCH_PAIRS` | `{pairs:[{left,right}]}` (client shuffles each column) | — | `{completed: true}` |
| `FILL_BLANK` | `{sentence: "Yo ___ estudiante.", options}` | `{answer}` | `{answer}` |
| `TYPE_ANSWER` | `{placeholder?}` | `{accepted}` | `{text}` |

### API (§6)

- The error body is always `{ "detail": { "code": "SOME_CODE", "message": "..." } }`. Never send stack traces to the client. Register exception handlers in `main.py`, including one for validation errors, so every error follows this format.
- Endpoints: `GET /api/health`, `GET /api/me`, `GET /api/course` (the entire path in **one** call), `GET /api/lessons/{id}`, `POST /api/lessons/{id}/start`, `POST /api/attempts/{id}/answer`, `POST /api/attempts/{id}/complete`, `POST /api/me/hearts/refill`, `GET /api/profile`, `GET /api/leaderboard` (with an `is_current_user` flag), `GET /api/achievements`.
- The completion summary shape is fixed by §6. Match it field for field (`xp_earned`, `perfect`, `already_completed`, `mistakes`, `accuracy`, `total_xp`, `streak{before,after,extended}`, `daily_goal{earned,goal,just_met}`, `skill{id,progress,state}`, `newly_unlocked_skill`, `new_achievements`).

### Data model (§4)

All 13 tables listed in §4 are normalized, with FKs, indexes on FK columns and the listed unique constraints. JSON columns are allowed **only** for exercise `payload`, `solution` and `attempt_answers.submitted`, never for user state.

### Seed data (§7)

`python -m app.seed --reset` must be idempotent.
- **Course and learner:** Spanish 🇪🇸, 3 units, 9 skills, 2 lessons per skill, 5–7 exercises per lesson. Every lesson uses ≥3 exercise types, and every type appears in Unit 1. French, Punjabi and English have 2 units × 3 skills × 2 lessons × 6 exercises each; skill `order_index` restarts at 1 in every course.
- **Spanish quality:** the Spanish must be correct: accents, `¿ ¡`, gender agreement.
- **Learner `arnav`:** Greetings COMPLETED (2/2), Introductions IN_PROGRESS (1/2), all other skills LOCKED. XP 45, gems 500, hearts 5, daily goal 20, streak 3. There are `daily_activity` rows for the **previous 3 days, not today**, and `last_activity_date` is yesterday. `FIRST_LESSON` and `STREAK_3` are unlocked and `PERFECT_LESSON` is **not**, so keep the seeded history consistent with that.
- **Seed dates:** compute them relative to "today" in `APP_TIMEZONE` when the seed runs. Re-seed before a demo, or the streak shows as broken.
- **Leaderboard:** 5 other users with XP 140, 95, 70, 38 and 20.

## Frontend conventions (§8)

- **Stack:** scaffold with `create-next-app` (TypeScript, Tailwind, App Router, ESLint). Use strict TS with no `any`. Use Nunito (or a similar rounded font) via `next/font`.
- **Before writing pages:** check the installed Next.js and Tailwind major versions. On Next 15+, route `params` is a Promise. On Tailwind v4, design tokens go in CSS (`@theme` in `globals.css`), not in `tailwind.config`.
- **Server state:** keep it in a small `UserStatsContext` that holds `/api/me` and exposes `refresh()`. Call `refresh()` after answers (hearts) and after completion. No Redux/Zustand.
- **`LessonPlayer`:** implement an explicit state machine: `INTRO → ANSWERING → CHECKING → FEEDBACK → … → SUBMITTING → COMPLETE`, plus `OUT_OF_HEARTS`. Never auto-advance.
- **Keyboard:** `Enter` = Check/Continue, `1–4` pick options.
- **`ExerciseRenderer`:** uses a `type → component` registry object. Adding a type means one component plus one registry entry.
- **Learning path:** a vertical zig-zag (sine-wave offsets), **not a grid**. Nodes have SVG progress rings and a state-specific style per state. Tapping a node opens a popover. On load, auto-scroll to the current skill.
- **Data views:** every data view has loading (skeleton), error (friendly message + Retry) and empty states. Buttons disable while a request is pending.
- **Visuals:** chunky 3D buttons (`border-b-4`; pressing translates the button down and removes the border), rounded-2xl cards, tap targets ≥44px. Use original SVG icons and mascot only. Animations are CSS only and must respect `prefers-reduced-motion`.
- **Accessibility:** semantic `<button>`s, labelled inputs, visible focus rings, `aria-live="polite"` on the feedback bar, and `aria-label` on icon-only controls. Check at 375px and 1440px.

## Known gotchas

- **Timezones on Windows:** a venv has no system tz database, so `zoneinfo.ZoneInfo("Asia/Kolkata")` fails without the `tzdata` package. Add `tzdata` to `requirements.txt`.
- **In-memory SQLite in tests:** use `sqlite://` with `poolclass=StaticPool` and `connect_args={"check_same_thread": False}`, or each connection gets its own empty DB. Override `get_db` (and `get_current_user` as needed) via `app.dependency_overrides`.
- **SQLite foreign keys:** SQLite ignores FKs unless `PRAGMA foreign_keys=ON` is set on connect. Use an engine `connect` event.
- **SQLite and timezones:** SQLite returns naive datetimes. Store UTC consistently and convert at the edges, so heart-regen math never mixes naive and aware values.
- **Frontend API URL:** `NEXT_PUBLIC_*` vars are inlined at build time, so rebuild after changing `NEXT_PUBLIC_API_URL`.
- **Git hygiene:** add `backend/app.db`, `duolingo/` (the venv), `node_modules/`, `.next/` and `.env` to `.gitignore`. Commit the `.env.example` files and `.claude/agents/`. Don't commit `.claude/settings.local.json`.

## Testing requirements (§9)

- **Backend (pytest):** use in-memory SQLite and fixed `today`/`now`. Cover:
  - normalization, accent notes, multiple accepted answers and word-bank order
  - streak cases, including display-as-0
  - hearts: deduction, floor, lazy regen, cap, refill with and without gems
  - a duplicate answer does not deduct twice
  - XP: base, perfect bonus and practice XP
  - completion idempotency
  - guards: unanswered or failed attempt, locked lesson, 0 hearts
  - skill state, progress and unlocks
  - daily goal `just_met` fires once
  - achievements unlock once
- **Smoke test:** `backend/scripts/smoke_test.py` runs against the live server and a fresh seed. It follows the exact flow in §9.2 (wrong answer costs a heart → complete → XP, streak 3→4, unlock → a second complete awards nothing → `/api/me` persisted).
- **Frontend:** `tsc --noEmit`, `lint` and `build` must all be clean. Run the browser journey in §9.4 with Playwright if it's available. Otherwise, state explicitly which steps were verified only via the API.

## Deliverables (§10, §12, §13)

- **`README.md`:** covers everything listed in §10, including tested setup commands for macOS/Linux **and** Windows and a 3-minute demo script.
- **`INTERVIEW_NOTES.md`:** written from the **actual code** (real file and function names). Includes Decisions, a security/integrity section and 20+ interview Q&As.
- **`.env.example` files:** one in `backend/` and one in `frontend/`.
- **Final report:** format it per §13. Include an honest status and checklist, run commands, deploy notes (Vercel + Render/Railway, and SQLite needing a persistent disk or seed-on-startup), the top 10 implementation details tied to files, and the demo script.
