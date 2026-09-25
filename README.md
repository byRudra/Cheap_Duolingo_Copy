# Duolingo (assessment build)

A Duolingo-inspired, gamified language-learning web app. It ships four courses (**Spanish**, **French**, **Punjabi** and **English**). You work through a winding path of skills in short lessons with five exercise types. Along the way you earn XP, keep a daily streak, spend hearts on mistakes, win hearts back in heart practice, hit a daily goal and unlock achievements. The mascot is **Pico**, an original SVG parrot (`frontend/components/Mascot.tsx`). The app has no Duolingo owl, logos or other artwork.

The FastAPI backend is the single source of truth. It owns every game rule (XP, hearts, streak, unlocks, achievements) and checks every answer. The React/Next.js frontend only renders and collects input.

> **Branding.** The spec asked for an original product name. At the user's explicit request the app is branded "Duolingo". The name is a one-line change in each half: `APP_NAME` in `frontend/lib/brand.ts` and `APP_NAME` in `backend/app/config.py` (also settable through the `APP_NAME` env var). The mascot, icons and artwork are all original.

---

## Features

- **Four courses**, each with its own path and progress. Switch with the flag button (right rail on desktop, top bar on mobile) or from Settings → Learning language. Progress in every course is kept.

  | Course | Units / skills / lessons / exercises | Notes |
  |---|---|---|
  | Spanish 🇪🇸 (demo course) | 3 / 9 / 18 / 108 | The seeded learner is part-way through it |
  | French 🇫🇷 | 2 / 6 / 12 / 72 | |
  | Punjabi | 2 / 6 / 12 / 72 | Gurmukhi script. Options include a romanization, and type-answer exercises also accept common romanized spellings |
  | English 🇬🇧 | 2 / 6 / 12 / 72 | A beginner course taught in English only |

  Content lives in `backend/app/content/<language>.py` and is registered in `backend/app/content/__init__.py`. Every course must pass `content/builders.validate_course` at seed time and in tests.
- **Learning path**: nodes sit on a vertical zig-zag (sine-wave offsets) with SVG progress rings and four states: `LOCKED`, `AVAILABLE`, `IN_PROGRESS` and `COMPLETED`. Tapping a node opens a popover, and the path auto-scrolls to the current skill.
- **Lesson player**: a full-screen explicit state machine (`INTRO → ANSWERING → CHECKING → FEEDBACK → … → SUBMITTING → COMPLETE`, plus `OUT_OF_HEARTS`) with a progress bar, a feedback bar and keyboard support (`Enter` = Check/Continue, `1`–`4` pick an option). Type-answer exercises show accented-letter buttons for Spanish and French.
- **Five exercise types**: multiple choice, word bank, match pairs, fill in the blank and type the answer. Every lesson uses at least three, and Unit 1 of every course uses all five.
- **Server-side answer checking**: normalization, multiple accepted answers, and accent-tolerant matching with a "Watch your accents" note. Accent forgiveness covers only Latin diacritics, so a missing Gurmukhi vowel sign is a wrong answer, not an accent slip.
- **Hearts**: a wrong answer costs one heart. Hearts regenerate lazily (one every `HEART_REGEN_MINUTES`) and can be refilled for 350 gems. At 0 hearts the out-of-hearts modal offers Refill, Practice and Return home.
- **Heart practice** (`/practice`): replays your weakest completed lesson in the current course, even at 0 hearts. Mistakes are free, and finishing restores one heart. It awards no XP and doesn't touch the streak, the daily goal or progress.
- **XP**: 10 for a first completion, +5 for a perfect lesson, 5 for a practice replay. All of it is computed on the server.
- **Streak and daily goal**: the streak extends once per calendar day in `APP_TIMEZONE` and shows as 0 once broken. The daily goal (10, 20, 30 or 50 XP) celebrates once, when it is crossed.
- **Skill unlocking**: in each course, skills unlock in order across units, and lessons unlock in order within a skill.
- **Achievements**: First Steps, Flawless, XP Hunter, On Fire and Dedicated. Each unlocks at most once and appears as a toast on the completion screen.
- **Settings** (all of them work and persist; nothing is "Coming soon"):
  - Profile: display name, avatar colour and daily goal, saved to the server.
  - Appearance: Light / Dark / System theme, stored per device.
  - Learning language: the course switcher, with per-course progress.
  - Notifications: a daily streak reminder (an in-app banner on the home screen, plus an optional browser notification at most once a day) and achievement alerts (whether completion toasts show).
  - Sound: short effects synthesized with the Web Audio API (`frontend/lib/sound.ts`), so no audio files ship.
  - Account: reset progress in the current course, or restore the whole demo.
- **Dark mode**: the same design tokens with dark values. An inline script sets `data-theme` on `<html>` before first paint, so the page never flashes the wrong theme.
- **Profile, leaderboard**: the profile shows stats, your courses and achievements (locked and unlocked). The leaderboard ranks the seeded learner among 5 seeded rivals, with the current user highlighted.
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
│   app/(main)/…  app/lesson/[id]  app/practice                │
│   context/UserStatsContext.tsx  ← /api/me, refresh()         │
│   lib/api.ts  typed fetch wrapper, throws ApiError(code)     │
│   lib/theme.ts (dark mode) · lib/sound.ts · lib/reminder.ts  │
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
│   lesson_service.py    start / practice / answer / complete  │
│   progress_service.py  skill + lesson state, unlocks,        │
│                        active course, course reset           │
│   gamification.py      hearts, streak, XP, goal, achievements│
└───────────────────────────┬──────────────────────────────────┘
┌───────────────────────────▼──────────────────────────────────┐
│ SQLAlchemy 2.x models (models.py) → SQLite backend/app.db    │
│   PRAGMA foreign_keys=ON · BEGIN IMMEDIATE per transaction   │
└──────────────────────────────────────────────────────────────┘
   backend/app/content/  course data + validate_course → seed.py
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
│   │   ├── config.py             # Settings: game constants, APP_NAME, env overrides
│   │   ├── database.py           # engine, SessionLocal, Base, get_db, FK pragma, BEGIN IMMEDIATE
│   │   ├── deps.py               # get_current_user (the auth seam), get_now (injectable clock)
│   │   ├── clock.py              # utc_now(), local_date() in APP_TIMEZONE
│   │   ├── errors.py             # AppError → {"detail": {"code", "message"}}
│   │   ├── models.py             # 13 tables
│   │   ├── schemas.py            # Pydantic v2 request/response models
│   │   ├── seed.py               # python -m app.seed [--reset]; restore_demo()
│   │   ├── content/              # spanish.py, french.py, punjabi.py, english.py,
│   │   │                         # builders.py (mc/wb/mp/fb/ta + validate_course), __init__.py (COURSES)
│   │   ├── routers/              # course.py, lessons.py, me.py, social.py
│   │   └── services/             # answer_check.py, lesson_service.py, progress_service.py, gamification.py
│   ├── tests/                    # conftest.py, helpers.py, test_*.py (267 tests)
│   └── scripts/smoke_test.py     # end-to-end check against a running server
└── frontend/
    ├── .env.example  next.config.ts  package.json
    ├── app/
    │   ├── layout.tsx            # Nunito font, THEME_INIT_SCRIPT, UserStatsProvider
    │   ├── globals.css           # Tailwind v4 @theme tokens, dark overrides, keyframes, reduced-motion
    │   ├── (main)/               # AppShell routes: page.tsx (path), profile/, leaderboard/, settings/
    │   ├── lesson/[id]/page.tsx  # full-screen lesson (async params)
    │   ├── practice/page.tsx     # full-screen heart practice
    │   ├── icon.svg  not-found.tsx
    ├── components/
    │   ├── lesson/               # LessonPlayer, ExerciseRenderer, FeedbackBar, LessonComplete, OutOfHeartsModal
    │   │   └── exercises/        # MultipleChoice, WordBank, MatchPairs, FillBlank, TypeAnswer, OptionCard, useNumberKeys
    │   ├── path/                 # LearningPath, SkillNode
    │   ├── home/RightRail.tsx    # course switcher, streak, daily goal, hearts + refill/practice
    │   ├── layout/               # AppShell (sidebar / bottom tabs), CourseSwitcher, StatPills
    │   ├── settings/             # SettingsView, ProfileSection, Toggle, shared, useSettingsSave
    │   ├── ui/                   # Button, Modal, ProgressRing, States, Countdown, CourseFlag, ThemeToggle, icons
    │   ├── leaderboard/  profile/
    │   └── Mascot.tsx            # Pico
    ├── context/UserStatsContext.tsx
    └── lib/                      # api.ts, types.ts, useApi.ts, shuffle.ts, brand.ts, theme.ts, sound.ts, reminder.ts
```

## Database schema (13 tables)

| Table | Purpose | Key constraints |
|---|---|---|
| `users` | Learner stats: `xp`, `gems`, `hearts`, `hearts_updated_at`, `streak`, `longest_streak`, `last_activity_date`, `daily_goal_xp`, `active_course_id`. Settings: `display_name`, `avatar_color`, `sound_effects`, `daily_reminder`, `achievement_alerts` | `username` unique; FK `active_course_id` (nullable) |
| `courses` | One row per course: `title`, `language_code`, `flag_emoji`, `description` | `language_code` unique |
| `units` | Course sections with a colour | FK `course_id`; unique (`course_id`, `order_index`) |
| `skills` | Path nodes. `order_index` runs across the whole course and restarts at 1 in each course | FK `unit_id`; `order_index` indexed |
| `lessons` | Lessons within a skill | FK `skill_id`; unique (`skill_id`, `order_index`) |
| `exercises` | `type`, `prompt`, JSON `payload` (sent to client), JSON `solution` (server only), `explanation` | FK `lesson_id`; unique (`lesson_id`, `order_index`) |
| `lesson_attempts` | One play-through: `status` (`IN_PROGRESS`/`COMPLETED`/`FAILED`), `mode` (`LESSON`/`PRACTICE`), `mistakes`, `xp_awarded` | FKs `user_id`, `lesson_id` |
| `attempt_answers` | Stored result per exercise: JSON `submitted`, `is_correct`, `note` | **unique (`attempt_id`, `exercise_id`)** |
| `user_lesson_progress` | First completion of a lesson, `best_mistakes` | unique (`user_id`, `lesson_id`) |
| `user_skill_progress` | `unlocked_at`, `lessons_completed` per skill | unique (`user_id`, `skill_id`) |
| `daily_activity` | `xp_earned`, `lessons_completed` per local day | unique (`user_id`, `date`) |
| `achievements` | Catalogue: `code`, `title`, `description`, `icon` | `code` unique |
| `user_achievements` | Unlocks with `unlocked_at` | unique (`user_id`, `achievement_id`) |

Every FK column is indexed. JSON columns are used only for `exercises.payload`, `exercises.solution` and `attempt_answers.submitted`, never for user state. The per-course uniqueness of `skills.order_index` is guaranteed by the seed (`seed._add_course` numbers skills 1..n per course), not by a DB constraint, because `skills` has no `course_id` column.

## API

Every error has the same body: `{"detail": {"code": "SOME_CODE", "message": "..."}}` (including 404, 405, 422 validation errors and unexpected 500s). Swagger UI is at `http://localhost:8000/docs`.

| Method | Path | Returns | Notable errors |
|---|---|---|---|
| GET | `/api/health` | `{"status": "ok"}` | |
| GET | `/api/me` | Learner stats with hearts regen and streak display applied on read, `next_heart_at`, `daily_goal{goal,earned,met}`, `streak_extended_today`, `today`, `active_course`, `settings` | `503 NOT_SEEDED` |
| PATCH | `/api/me/settings` | Partial update of `display_name` (1–30 chars), `avatar_color` (`#RRGGBB`), `daily_goal_xp` (10/20/30/50), `sound_effects`, `daily_reminder`, `achievement_alerts`; returns the updated `/api/me` body | `422 VALIDATION_ERROR` |
| POST | `/api/me/course` | Body `{course_id}`. Switches the active course; returns the updated `/api/me` body | `404 COURSE_NOT_FOUND` |
| POST | `/api/me/reset` | Body `{scope: "course" \| "demo"}` → `{scope, message}`. `course` clears lesson/skill progress in the active course (XP, streak, gems and achievements stay). `demo` wipes every table and reseeds | `403 DEMO_RESET_DISABLED` (demo scope when `ALLOW_DEMO_RESET=false`), `422 VALIDATION_ERROR` |
| POST | `/api/me/hearts/refill` | `{hearts, gems, next_heart_at}` | `400 INSUFFICIENT_GEMS`, `400 HEARTS_FULL` |
| GET | `/api/course` | The active course's entire path in one call: units → skills (state, progress %, `next_lesson_id`) → lessons (status), plus `current_skill_id` | |
| GET | `/api/courses` | Every course with `is_active`, `lessons_completed`, `lessons_total` and `progress` | |
| GET | `/api/lessons/{id}` | Lesson intro metadata (status, `is_practice`, `xp_reward`, exercise count, its course) | `404 LESSON_NOT_FOUND` |
| POST | `/api/lessons/{id}/start` | New `IN_PROGRESS` attempt (`mode: "LESSON"`) + exercises **without solutions** | `403 LESSON_LOCKED`, `409 OUT_OF_HEARTS` |
| POST | `/api/practice/start` | Heart-practice attempt (`mode: "PRACTICE"`) on the weakest completed lesson of the active course (the first lesson if none). Allowed at 0 hearts | |
| POST | `/api/attempts/{id}/answer` | `{correct, correct_answer, explanation, note, hearts, out_of_hearts}` | `404 ATTEMPT_NOT_FOUND`, `400 EXERCISE_NOT_IN_LESSON`, `409 ATTEMPT_NOT_IN_PROGRESS`, `422 INVALID_ANSWER` |
| POST | `/api/attempts/{id}/complete` | Completion summary: `xp_earned`, `perfect`, `already_completed`, `mistakes`, `accuracy`, `total_xp`, `streak{before,after,extended}`, `daily_goal{earned,goal,just_met}`, `skill{id,progress,state}`, `newly_unlocked_skill`, `new_achievements`, plus `mode`, `hearts` and `hearts_restored` | `409 INCOMPLETE_ATTEMPT`, `409 ATTEMPT_FAILED`, `409 LESSON_LOCKED` (re-locked by a course reset) |
| GET | `/api/profile` | Stats, active course, every course's progress, and all achievements (locked + unlocked) | |
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

> If the database is empty when the server starts, the backend seeds it automatically (`AUTO_SEED=true`), so `python -m app.seed --reset` is mainly for **resetting** the demo. Settings → Account → **Restore demo data** does the same from the browser. Seed dates are relative to "today" in `APP_TIMEZONE` when the seed runs. **Re-seed before a demo**, or the seeded streak will show as broken.

The seed prints one line per course:

```text
Seeded Spanish course: 3 units, 9 skills, 108 exercises
Seeded French course: 2 units, 6 skills, 72 exercises
Seeded Punjabi course: 2 units, 6 skills, 72 exercises
Seeded English course: 2 units, 6 skills, 72 exercises
Learner 'arnav' + 5 rivals.
```

### Tests and checks

Run these from `backend/` with the `duolingo` venv active:

```bash
pytest                                        # full suite: 267 passed
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

- **Fresh-clone run (Windows 11, PowerShell).** Every command above was run in a new clone with a new `duolingo` venv, on ports 8001/3001: `pip install`, `seed --reset` (and a second plain `seed`, which is a no-op), `pytest` (264 passed at the time; the suite is now 267), the `-k streak` subset, `uvicorn --reload`, `/api/health`, `/docs`, the smoke test (22/22), `npm install`, `tsc`, `lint`, `build`, `npm start` and `npm run dev`. The new endpoints were exercised with curl: `/api/courses`, `POST /api/me/course`, `PATCH /api/me/settings` (plus rejected goals and ignored `xp`/`hearts`/`gems` keys), `/api/practice/start`, both reset scopes, `ALLOW_DEMO_RESET=false` → `403 DEMO_RESET_DISABLED`, the CORS preflight for `PATCH`, and AUTO_SEED on an empty DB. The bash smoke-test variant (inline `API_URL=…`, with the venv activated from Git Bash) was also run.
- **macOS/Linux.** The `source duolingo/bin/activate` path could not be exercised on the Windows test machine.
- **Browser journeys (Playwright, against the production build, run in the main session).** Zero console errors across all three:
  - **Original journey, 37/37:** a wrong answer costs exactly −1 heart, a full lesson plays end to end, streak 3 → 4 and the Common Words unlock, state persists across a hard refresh, and draining hearts shows the modal and the refill.
  - **Perfect lesson, 9/9:** +15 XP with the Flawless toast.
  - **New features, 32/32:** dark mode persists across reloads, settings persist, a perfect French lesson gives +15 XP, a Punjabi lesson plays, the course switcher works, heart practice takes hearts 4 → 5, course reset, demo restore, and no horizontal overflow at 375px in dark mode.

## Environment variables

**Backend** (`backend/.env`, all optional, read by `app/config.py → Settings`):

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./app.db` | SQLite file. Relative paths resolve from `backend/`. The engine setup is SQLite-specific. |
| `CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated allowed browser origins (methods `GET`, `POST`, `PATCH`) |
| `AUTO_SEED` | `true` | Seed on startup when the DB has no course |
| `DEMO_USERNAME` | `arnav` | The learner `get_current_user` returns |
| `APP_NAME` | `Duolingo` | Product name in the API title and the seed CLI help |
| `ALLOW_DEMO_RESET` | `true` | Allows `POST /api/me/reset {"scope": "demo"}`, which wipes every table. Set `false` on a public deploy |
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

- **Branding.** The spec asked for an original name; the user asked for "Duolingo". Changing it is one constant per side (see the note at the top). The mascot and artwork stay original.
- **Single seeded user, no auth.** Every request acts as `arnav` (`deps.get_current_user`). That function is the only auth seam.
- **Four fixed courses, one active at a time.** The learner's active course is `users.active_course_id`, falling back to the first course. Spanish is the spec's demo course; the seeded learner starts fresh in French, Punjabi and English. XP, streak, hearts, gems, the daily goal and achievements are shared across courses.
- **Mocked gems.** Gems are seeded at 500 and are never earned. Their only use is the 350-gem heart refill.
- **Lazy heart regeneration.** Hearts are recomputed from `hearts_updated_at` on every read and before every deduction, with no background job.
- **Seeded leaderboard.** Five fixed rivals (XP 140, 95, 70, 38, 20). There are no leagues, weeks or friends.
- **No audio content.** There are no listening or speaking exercises and no media assets. The only sounds are short synthesized UI effects.
- **Per-device preferences.** The theme lives in `localStorage` on each device. Every other setting is stored on the server.
- **Reminders need the tab.** The streak reminder is an in-app banner, plus a browser notification when the home page is opened and permission is granted. There is no push service or background job.
- **Streak freezes and leagues are out of scope.**

## Deploying

- **Frontend on Vercel.**
  - Set the root directory to `frontend/`.
  - Set `NEXT_PUBLIC_API_URL` to the backend URL, and redeploy (rebuild) whenever it changes.
- **Backend on Render or Railway.**
  - Set the root directory to `backend/`.
  - Build command: `pip install -r requirements.txt`.
  - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
  - Set `CORS_ORIGINS` to the Vercel URL.
  - Set `ALLOW_DEMO_RESET=false` so a visitor can't wipe the database from Settings.
- **SQLite on a host.** Either attach a persistent disk and point `DATABASE_URL` at it, or accept an ephemeral filesystem. On an ephemeral filesystem, `AUTO_SEED=true` re-seeds the demo on each cold start (progress resets on restart).

## Future improvements

- Real authentication (JWT/OAuth) replacing `get_current_user`, with multiple users.
- PostgreSQL + Alembic migrations, and row-level locking instead of SQLite `BEGIN IMMEDIATE`.
- Server-verified match pairs (submit the pairing, not just `{completed: true}`).
- Audio prompts and listening/speaking exercises served from object storage/CDN.
- Weekly leagues on a Redis sorted-set leaderboard, friends, and streak freezes bought with gems that are actually earned.
- Real push reminders (a scheduled job + Web Push) instead of the in-app banner.
- A content authoring tool that writes the `content/` format and runs `validate_course`.
- Spaced-repetition practice of weak words (heart practice currently replays a whole lesson).

## 3-minute demo script

**Before you start:** reseed with `python -m app.seed --reset` (or Settings → Account → Restore demo data). For the heart-regen countdown, put `HEART_REGEN_MINUTES=1` in `backend/.env` and restart uvicorn. Open `http://localhost:3000` in light mode.

1. **Path (0:00–0:20).** The path auto-scrolls to Introductions.
   - Greetings is **COMPLETED** (full ring), Introductions is **IN_PROGRESS** (50% ring) and Common Words and later skills are **LOCKED**.
   - The right rail shows the Spanish flag, a 3-day streak, a 0/20 XP daily goal and 5 hearts. The streak reminder banner sits above the path. Tap a locked node to show its popover.
2. **Lesson with a mistake (0:20–1:00).** Tap Introductions → Start ("Where are you from?").
   - Answer one question wrong: the feedback bar turns red, shows the correct answer, and hearts drop 5 → 4.
   - Show the other exercise types: word bank, match pairs (a mismatch shakes but costs no heart), fill in the blank, and type the answer (typing `de donde eres` is accepted with the note "Watch your accents: ¿De dónde eres?").
   - The completion screen shows +10 XP, streak 3 → 4, daily goal 10/20 and "New skill unlocked: Common Words".
3. **Persistence (1:00–1:10).** Hard-refresh the page. XP, streak, hearts and the unlocked Common Words node are all still there, and the reminder banner is gone.
4. **Perfect lesson (1:10–1:35).** Play Common Words → "Yes, no, please" with no mistakes.
   - The screen shows +15 XP ("Perfect lesson!") and the daily goal complete celebration (25/20).
   - Achievement toasts appear for **Flawless** and **Dedicated** (5 distinct lessons).
5. **Out of hearts, practice, refill (1:35–2:05).** Start the next lesson and answer gradable exercises wrong until hearts reach 0.
   - The out-of-hearts modal shows the next-heart countdown. Tap **Practice to earn a heart**: mistakes cost nothing, and finishing shows "+1 heart" and awards no XP.
   - Back on the home screen, refill from the right rail for 350 gems (500 → 150). 150 gems can't pay for another refill, so the next time hearts drop the Refill button is disabled.
6. **Languages, dark mode, settings (2:05–2:35).**
   - Switch the theme to **Dark** in the sidebar and refresh: it stays dark with no flash.
   - Open the flag switcher and pick **French**: a fresh French path, while Spanish progress is kept. Pick **Punjabi** to show Gurmukhi lessons with romanized hints.
   - In Settings, change the daily goal to 30 and toggle sound effects. Both survive a refresh.
7. **Profile and leaderboard (2:35–2:50).**
   - The profile shows total XP, streak stats, per-course progress and achievements (unlocked and locked).
   - On the leaderboard, Arnav is highlighted among the rivals.
8. **Mobile (2:50–3:00).** Narrow the browser to 375px. The sidebar becomes a bottom tab bar, and the stats and flag switcher move into the top bar.
