# Habla

A Duolingo-inspired, gamified Spanish-learning web app. You work through a winding path of skills in short lessons with five exercise types. Along the way you earn XP, keep a daily streak, spend hearts on mistakes, hit a daily goal and unlock achievements. The mascot is **Pico**, an original SVG parrot (`frontend/components/Mascot.tsx`).

The FastAPI backend is the single source of truth. It owns every game rule (XP, hearts, streak, unlocks, achievements) and checks every answer. The React/Next.js frontend only renders and collects input.

---

## Features

- **Learning path**: one Spanish course with 3 units, 9 skills, 18 lessons and 108 exercises. Nodes sit on a vertical zig-zag (sine-wave offsets) with SVG progress rings and four states: `LOCKED`, `AVAILABLE`, `IN_PROGRESS` and `COMPLETED`. Tapping a node opens a popover, and the path auto-scrolls to the current skill.
- **Lesson player**: a full-screen explicit state machine (`INTRO → ANSWERING → CHECKING → FEEDBACK → … → SUBMITTING → COMPLETE`, plus `OUT_OF_HEARTS`) with a progress bar, a feedback bar and keyboard support (`Enter` = Check/Continue, `1`–`4` pick an option).
- **Five exercise types**: multiple choice, word bank, match pairs, fill in the blank and type the answer. Every seeded lesson uses all five.
- **Server-side answer checking**: normalization, multiple accepted answers, and accent-tolerant matching with a "Watch your accents" note.
- **Hearts**: a wrong answer costs one heart. Hearts regenerate lazily (one every `HEART_REGEN_MINUTES`) and can be refilled for 350 gems. At 0 hearts the out-of-hearts modal appears.
- **XP**: 10 for a first completion, +5 for a perfect lesson, 5 for a practice replay. All of it is computed on the server.
- **Streak and daily goal**: the streak extends once per calendar day in `APP_TIMEZONE` and shows as 0 once broken. The 20 XP daily goal celebrates exactly once, when it is crossed.
- **Skill unlocking**: skills unlock sequentially across the whole course, and lessons unlock sequentially within a skill.
- **Achievements**: First Steps, Flawless, XP Hunter, On Fire and Dedicated. Each unlocks at most once and appears as a toast on the completion screen.
- **Profile, leaderboard, settings**: the profile shows stats and achievements. The leaderboard ranks the seeded learner among 5 seeded rivals, with the current user highlighted. Settings are preview-only "Coming soon" toggles.
- **Responsive and accessible**: a left sidebar at ≥1024px and a bottom tab bar on mobile. Every data view has loading skeletons, a friendly error with Retry, and empty states. Animations are CSS-only and respect `prefers-reduced-motion`. The feedback bar uses `aria-live="polite"`.

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | Next.js 16.3 (App Router) · React 19.2 · TypeScript (strict) · Tailwind CSS v4 (CSS-first `@theme` tokens) · Nunito via `next/font` · ESLint 9 |
| Backend | Python 3.11+ (tested on 3.14.0) · FastAPI 0.141 · Uvicorn 0.54 · Pydantic v2 + pydantic-settings · SQLAlchemy 2.1 |
| Database | SQLite (`backend/app.db`) |
| Tests | pytest 9 with in-memory SQLite and a frozen clock · `httpx` smoke script against the live server |

## Architecture

```text
┌──────────────────────────────────────────────────────────────┐
│ frontend/  Next.js App Router (React, TS strict, Tailwind v4)│
│   app/(main)/…  app/lesson/[id]   components/…               │
│   context/UserStatsContext.tsx  ← /api/me, refresh()         │
│   lib/api.ts  typed fetch wrapper, throws ApiError(code)     │
└───────────────────────────┬──────────────────────────────────┘
                            │ REST / JSON  (CORS: CORS_ORIGINS)
┌───────────────────────────▼──────────────────────────────────┐
│ backend/app/main.py  FastAPI app, CORS, error handlers       │
│ backend/app/routers/  course · lessons · me · social         │
│      thin: parse → Depends(get_db, get_current_user,         │
│            get_now) → call service → return Pydantic schema  │
└───────────────────────────┬──────────────────────────────────┘
┌───────────────────────────▼──────────────────────────────────┐
│ backend/app/services/  ALL game rules                        │
│   answer_check.py      normalize(), check_answer()           │
│   lesson_service.py    start / answer / complete attempts    │
│   progress_service.py  derive skill + lesson state, unlocks  │
│   gamification.py      hearts, streak, XP, goal, achievements│
└───────────────────────────┬──────────────────────────────────┘
┌───────────────────────────▼──────────────────────────────────┐
│ SQLAlchemy 2.x models (models.py) → SQLite backend/app.db    │
│   PRAGMA foreign_keys=ON · BEGIN IMMEDIATE per transaction   │
└──────────────────────────────────────────────────────────────┘
```

## Project structure

```text
.
├── README.md  INTERVIEW_NOTES.md  CLAUDE.md
├── duolingo/                     # Python venv (created by you, git-ignored)
├── backend/
│   ├── .env.example  requirements.txt  pytest.ini
│   ├── app/
│   │   ├── main.py               # app, lifespan (create tables + AUTO_SEED), CORS, error handlers
│   │   ├── config.py             # Settings: game constants + env overrides
│   │   ├── database.py           # engine, SessionLocal, Base, get_db, FK pragma, BEGIN IMMEDIATE
│   │   ├── deps.py               # get_current_user (the auth seam), get_now (injectable clock)
│   │   ├── clock.py              # utc_now(), local_date() in APP_TIMEZONE
│   │   ├── errors.py             # AppError → {"detail": {"code", "message"}}
│   │   ├── models.py             # 13 tables
│   │   ├── schemas.py            # Pydantic v2 request/response models
│   │   ├── seed.py               # python -m app.seed [--reset]
│   │   ├── routers/              # course.py, lessons.py, me.py, social.py
│   │   └── services/             # answer_check.py, lesson_service.py, progress_service.py, gamification.py
│   ├── tests/                    # conftest.py, helpers.py, test_*.py (167 tests)
│   └── scripts/smoke_test.py     # end-to-end check against a running server
└── frontend/
    ├── .env.example  next.config.ts  package.json
    ├── app/
    │   ├── layout.tsx            # Nunito font, UserStatsProvider
    │   ├── globals.css           # Tailwind v4 @theme tokens, keyframes, reduced-motion
    │   ├── (main)/               # AppShell routes: page.tsx (path), profile/, leaderboard/, settings/
    │   ├── lesson/[id]/page.tsx  # full-screen lesson (async params)
    │   └── not-found.tsx
    ├── components/
    │   ├── lesson/               # LessonPlayer, ExerciseRenderer, FeedbackBar, LessonComplete, OutOfHeartsModal
    │   │   └── exercises/        # MultipleChoice, WordBank, MatchPairs, FillBlank, TypeAnswer, OptionCard, useNumberKeys
    │   ├── path/                 # LearningPath, SkillNode
    │   ├── home/RightRail.tsx    # streak, daily goal, hearts + refill
    │   ├── layout/               # AppShell (sidebar / bottom tabs), StatPills
    │   ├── ui/                   # Button, Modal, ProgressRing, States, Countdown, CourseFlag, icons
    │   ├── leaderboard/  profile/
    │   └── Mascot.tsx            # Pico
    ├── context/UserStatsContext.tsx
    └── lib/                      # api.ts, types.ts, useApi.ts, shuffle.ts
```

## Database schema (13 tables)

| Table | Purpose | Key constraints |
|---|---|---|
| `users` | Learner stats: `xp`, `gems`, `hearts`, `hearts_updated_at`, `streak`, `longest_streak`, `last_activity_date`, `daily_goal_xp` | `username` unique |
| `courses` | The course (Spanish, `es`) | |
| `units` | Course sections with a colour | FK `course_id`; unique (`course_id`, `order_index`) |
| `skills` | Path nodes | FK `unit_id`; `order_index` unique **course-wide** |
| `lessons` | Lessons within a skill | FK `skill_id`; unique (`skill_id`, `order_index`) |
| `exercises` | `type`, `prompt`, JSON `payload` (sent to client), JSON `solution` (server only), `explanation` | FK `lesson_id`; unique (`lesson_id`, `order_index`) |
| `lesson_attempts` | One play-through: `status` (`IN_PROGRESS`/`COMPLETED`/`FAILED`), `mistakes`, `xp_awarded` | FKs `user_id`, `lesson_id` |
| `attempt_answers` | Stored result per exercise: JSON `submitted`, `is_correct`, `note` | **unique (`attempt_id`, `exercise_id`)** |
| `user_lesson_progress` | First completion of a lesson, `best_mistakes` | unique (`user_id`, `lesson_id`) |
| `user_skill_progress` | `unlocked_at`, `lessons_completed` per skill | unique (`user_id`, `skill_id`) |
| `daily_activity` | `xp_earned`, `lessons_completed` per local day | unique (`user_id`, `date`) |
| `achievements` | Catalogue: `code`, `title`, `description`, `icon` | `code` unique |
| `user_achievements` | Unlocks with `unlocked_at` | unique (`user_id`, `achievement_id`) |

Every FK column is indexed. JSON columns are used only for `exercises.payload`, `exercises.solution` and `attempt_answers.submitted`, never for user state.

## API

Every error has the same body: `{"detail": {"code": "SOME_CODE", "message": "..."}}` (including 404, 405, 422 validation errors and unexpected 500s). Swagger UI is at `http://localhost:8000/docs`.

| Method | Path | Returns | Notable errors |
|---|---|---|---|
| GET | `/api/health` | `{"status": "ok"}` | |
| GET | `/api/me` | Learner stats with hearts regen and streak display applied on read, `next_heart_at`, `daily_goal{goal,earned,met}` | `503 NOT_SEEDED` |
| GET | `/api/course` | The entire path in one call: units → skills (state, progress %, `next_lesson_id`) → lessons (status), plus `current_skill_id` | |
| GET | `/api/lessons/{id}` | Lesson intro metadata (status, `is_practice`, `xp_reward`, exercise count) | `404 LESSON_NOT_FOUND` |
| POST | `/api/lessons/{id}/start` | New `IN_PROGRESS` attempt + exercises **without solutions** | `403 LESSON_LOCKED`, `409 OUT_OF_HEARTS` |
| POST | `/api/attempts/{id}/answer` | `{correct, correct_answer, explanation, note, hearts, out_of_hearts}` | `400 EXERCISE_NOT_IN_LESSON`, `409 ATTEMPT_NOT_IN_PROGRESS`, `422 INVALID_ANSWER` |
| POST | `/api/attempts/{id}/complete` | Completion summary: `xp_earned`, `perfect`, `already_completed`, `mistakes`, `accuracy`, `total_xp`, `streak{before,after,extended}`, `daily_goal{earned,goal,just_met}`, `skill{id,progress,state}`, `newly_unlocked_skill`, `new_achievements` | `409 INCOMPLETE_ATTEMPT`, `409 ATTEMPT_FAILED` |
| POST | `/api/me/hearts/refill` | `{hearts, gems, next_heart_at}` | `400 INSUFFICIENT_GEMS`, `400 HEARTS_FULL` |
| GET | `/api/profile` | Stats, course info and all achievements (locked + unlocked) | |
| GET | `/api/leaderboard` | Everyone ranked by XP, with `is_current_user` | |
| GET | `/api/achievements` | Achievement catalogue with `unlocked`/`unlocked_at` | |

---

## Setup

Prerequisites: **Python 3.11+** (tested with 3.14.0), **Node.js 20.9+** (Next.js 16's minimum; tested with 22.20.0 / npm 11.7.0) and git. The backend runs on port `8000` and the frontend on port `3000`.

The Python virtual environment is named **`duolingo`** and lives at the repo root. Create it once and use it for every backend command.

### Windows (PowerShell)

```powershell
# from the repo root
python -m venv duolingo
.\duolingo\Scripts\Activate.ps1
# If activation is blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
# (cmd.exe users: duolingo\Scripts\activate.bat)

# Backend (terminal 1)
cd backend
pip install -r requirements.txt
Copy-Item .env.example .env          # optional: set HEART_REGEN_MINUTES=1 for demos
python -m app.seed --reset           # creates/overwrites backend/app.db
uvicorn app.main:app --reload --port 8000
# API: http://localhost:8000   Swagger UI: http://localhost:8000/docs
```

```powershell
# Frontend (terminal 2, from the repo root)
cd frontend
npm install
Copy-Item .env.example .env.local    # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev                          # http://localhost:3000
```

### macOS / Linux (bash/zsh)

```bash
# from the repo root
python3 -m venv duolingo
source duolingo/bin/activate

# Backend (terminal 1)
cd backend
pip install -r requirements.txt
cp .env.example .env                 # optional: set HEART_REGEN_MINUTES=1 for demos
python -m app.seed --reset
uvicorn app.main:app --reload --port 8000
```

```bash
# Frontend (terminal 2, from the repo root)
cd frontend
npm install
cp .env.example .env.local
npm run dev                          # http://localhost:3000
```

> If the database is empty when the server starts, the backend seeds it automatically (`AUTO_SEED=true`), so `python -m app.seed --reset` is mainly for **resetting** the demo. Seed dates are relative to "today" in `APP_TIMEZONE` when the seed runs. **Re-seed before a demo**, or the seeded streak will show as broken.

### Tests and checks

Run these from `backend/` with the `duolingo` venv active:

```bash
pytest                                        # full suite: 167 passed
pytest tests/test_gamification.py -k streak   # one file / a subset
```

To run the smoke test, reseed and restart the server, then run the script in another terminal:

```bash
python -m app.seed --reset
uvicorn app.main:app --port 8000              # terminal 1
python scripts/smoke_test.py                  # terminal 2 → "SMOKE TEST PASSED" (22 checks)
```

The smoke test reads exercise solutions straight from the local `app.db` (test-only knowledge), so run it right after `seed --reset`, against the server that uses that same database. To target another port, set `API_URL`:

```powershell
$env:API_URL = "http://localhost:8001"; python scripts/smoke_test.py   # PowerShell
```
```bash
API_URL=http://localhost:8001 python scripts/smoke_test.py             # bash
```

Frontend checks, from `frontend/`:

```bash
npx tsc --noEmit
npm run lint
npm run build          # production build; must pass
npm start              # serve the production build on :3000
```

### Verified

- **Fresh-clone run (Windows 11, PowerShell).** Every command above was run in a new clone with a new `duolingo` venv: `pip install`, `seed --reset`, `pytest` (167 passed), `uvicorn`, `/api/health`, `/api/course`, `/docs`, the smoke test (22/22), `npm ci`, `tsc`, `lint`, `build`, `npm start` and `npm run dev`. The bash variants (`cp`, inline `API_URL=…`, AUTO_SEED on an empty DB) were also run in Git Bash.
- **macOS/Linux.** The `source duolingo/bin/activate` path could not be exercised on the Windows test machine.
- **Browser journey (Playwright, against the production build).** 46 checks passed, including:
  - a wrong answer costs exactly −1 heart
  - a full lesson plays end to end
  - streak 3 → 4 and the Common Words unlock
  - state persists across a hard refresh
  - draining hearts shows the modal, and refill works
  - a perfect lesson gives +15 XP with the Flawless toast
  - a practice replay gives +5 XP
  - the daily goal's `just_met` fires once
  - profile, leaderboard and settings render
  - no horizontal overflow at 375px
  - zero console errors

## Environment variables

**Backend** (`backend/.env`, all optional, read by `app/config.py → Settings`):

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./app.db` | SQLite file. Relative paths resolve from `backend/`. The engine setup is SQLite-specific. |
| `CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated allowed browser origins |
| `AUTO_SEED` | `true` | Seed on startup when the DB has no course |
| `DEMO_USERNAME` | `arnav` | The learner `get_current_user` returns |
| `MAX_HEARTS` | `5` | Heart cap |
| `HEART_REGEN_MINUTES` | `30` | Minutes per regenerated heart (`1` is handy for demos) |
| `HEART_REFILL_GEM_COST` | `350` | Gem price of a full refill |
| `BASE_LESSON_XP` | `10` | XP for a first completion |
| `PERFECT_BONUS_XP` | `5` | Extra XP for a first completion with 0 mistakes |
| `PRACTICE_XP` | `5` | XP for replaying a completed lesson (`0` disables) |
| `DEFAULT_DAILY_GOAL_XP` | `20` | Daily goal for seeded users |
| `APP_TIMEZONE` | `Asia/Kolkata` | Defines "today" for streaks and the daily goal |

The smoke script also reads `API_URL` (default `http://localhost:8000`) from the shell environment, not from `.env`. The pytest suite pins its own values in `tests/conftest.py`, so a demo `.env` never affects tests.

**Frontend** (`frontend/.env.local`):

| Variable | Default | Meaning |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend base URL. Next.js inlines it at build time, so **rebuild** after changing it. |

## Assumptions

- **Single seeded user, no auth.** Every request acts as `arnav` (`deps.get_current_user`). That function is the only auth seam.
- **One course.** Spanish for English speakers. The backend serves the first course in the table.
- **Mocked gems.** Gems are seeded at 500 and are never earned. Their only use is the 350-gem heart refill.
- **Lazy heart regeneration.** Hearts are recomputed from `hearts_updated_at` on every read and before every deduction, with no background job.
- **Seeded leaderboard.** Five fixed rivals (XP 140, 95, 70, 38, 20). There are no leagues, weeks or friends.
- **No audio.** There are no listening or speaking exercises and no media assets.
- **Streak freeze, leagues and settings persistence are out of scope.** The settings toggles are preview-only.

## Deploying

- **Frontend on Vercel.**
  - Set the root directory to `frontend/`.
  - Set `NEXT_PUBLIC_API_URL` to the backend URL, and redeploy (rebuild) whenever it changes.
- **Backend on Render or Railway.**
  - Set the root directory to `backend/`.
  - Build command: `pip install -r requirements.txt`.
  - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
  - Set `CORS_ORIGINS` to the Vercel URL.
- **SQLite on a host.** Either attach a persistent disk and point `DATABASE_URL` at it, or accept an ephemeral filesystem. On an ephemeral filesystem, `AUTO_SEED=true` re-seeds the demo on each cold start (progress resets on restart).

## Future improvements

- Real authentication (JWT/OAuth) replacing `get_current_user`, with multiple users and courses.
- PostgreSQL + Alembic migrations, and row-level locking instead of SQLite `BEGIN IMMEDIATE`.
- Server-verified match pairs (submit the pairing, not just `{completed: true}`).
- Audio prompts and listening/speaking exercises served from object storage/CDN.
- Weekly leagues on a Redis sorted-set leaderboard, friends, and streak freezes bought with gems that are actually earned.
- Persisted settings (sound effects, daily goal choice) and spaced-repetition practice of weak words.

## 3-minute demo script

**Before you start:** reseed with `python -m app.seed --reset`. For the heart-regen countdown, put `HEART_REGEN_MINUTES=1` in `backend/.env` and restart uvicorn. Then open `http://localhost:3000`.

1. **Path (0:00–0:30).** The path auto-scrolls to Introductions.
   - Greetings is **COMPLETED** (full ring), Introductions is **IN_PROGRESS** (50% ring) and Common Words and later skills are **LOCKED**.
   - The right rail shows a 3-day streak, a 0/20 XP daily goal and 5 hearts. Tap a locked node to show its popover.
2. **Lesson with a mistake (0:30–1:20).** Tap Introductions → Start ("Where are you from?").
   - Answer one question wrong: the feedback bar turns red, shows the correct answer, and hearts drop 5 → 4.
   - Show the other exercise types: word bank, match pairs (a mismatch shakes but costs no heart), fill in the blank, and type the answer (typing `de donde eres` is accepted with the note "Watch your accents: ¿De dónde eres?").
   - The completion screen shows +10 XP, streak 3 → 4, daily goal 10/20 and "New skill unlocked: Common Words".
3. **Persistence (1:20–1:30).** Hard-refresh the page. XP, streak, hearts and the unlocked Common Words node are all still there.
4. **Perfect lesson (1:30–2:00).** Play Common Words → "Yes, no, please" with no mistakes.
   - The screen shows +15 XP ("Perfect lesson!") and the daily goal complete celebration (25/20).
   - Achievement toasts appear for **Flawless** and **Dedicated** (5 distinct lessons).
5. **Out of hearts (2:00–2:30).** Start the next lesson and answer gradable exercises wrong until hearts reach 0.
   - The out-of-hearts modal shows the next-heart countdown. Refill for 350 gems (500 → 150).
   - A second refill is disabled because there are too few gems.
6. **Profile, leaderboard, settings (2:30–2:50).**
   - The profile shows total XP, streak stats, lessons and skills completed, and achievements (unlocked and locked).
   - On the leaderboard, Arnav is highlighted among the rivals.
   - Settings shows the "Coming soon" toggles.
7. **Mobile (2:50–3:00).** Narrow the browser to 375px. The sidebar becomes a bottom tab bar and the stats move into the top bar.
