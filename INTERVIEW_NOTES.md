# Habla: Interview Notes

These notes are written from the code as committed. Paths are relative to the repo root.

---

## 1. Architecture and data flow

```text
Browser (Next.js 16 App Router, React 19, TS strict, Tailwind v4)
  app/(main)/page.tsx ─ useApi(api.course) ──┐
  context/UserStatsContext.tsx ─ api.me() ───┤  lib/api.ts  request<T>()
  components/lesson/LessonPlayer.tsx ────────┤  → fetch(NEXT_PUBLIC_API_URL + path)
                                             │  → ApiError(status, code, message)
                                             ▼
FastAPI  backend/app/main.py
  CORSMiddleware (outermost) → unhandled_error_middleware → routers
  routers/course.py · lessons.py · me.py · social.py
     Depends(get_db) · Depends(get_current_user) · Depends(get_now)
                                             ▼
services/  lesson_service · progress_service · gamification · answer_check
                                             ▼
SQLAlchemy 2.x ORM (models.py) → SQLite backend/app.db
  database.py: PRAGMA foreign_keys=ON on connect; BEGIN IMMEDIATE on begin
```

**A typical request.** Take `POST /api/attempts/{id}/answer`:

1. `routers/lessons.py:answer_exercise` validates the body as `schemas.AnswerIn` (`exercise_id`, `answer` dict).
2. It resolves the session, the learner and `now` through dependencies, then calls `lesson_service.submit_answer`.
3. The service loads the attempt and checks that it belongs to the user and that the exercise belongs to the attempt's lesson.
4. It returns the stored result if this exercise was already answered. Otherwise it grades with `answer_check.check_answer`, applies heart regen and any deduction, inserts an `AttemptAnswer` and commits.
5. The router returns `schemas.AnswerOut`.

**Layering rule.** Routers are thin (parse, call a service, return a schema). All rules live in `services/`. Rule functions take `now`/`today` as parameters. The only clock reads are `clock.utc_now()`, called through `deps.get_now`, and the seed's default `now`.

**Startup.** The `lifespan` hook in `main.py` runs `Base.metadata.create_all(engine)`. If `settings.AUTO_SEED` is set and `seed.is_seeded()` is false, it runs `seed.seed()`, so an empty DB on a fresh host becomes a working demo.

---

## 2. Tables and why each exists (`backend/app/models.py`)

| Table | Why it exists |
|---|---|
| `users` | Holds all learner state as typed columns. `hearts` + `hearts_updated_at` drive lazy regen. `last_activity_date` drives the streak. `daily_goal_xp` is per-user. |
| `courses` → `units` → `skills` → `lessons` → `exercises` | Content hierarchy with `order_index` at every level. `skills.order_index` is unique **course-wide**, so unlocking is a single ordered walk across units. |
| `exercises` | `payload` (JSON, safe to send) and `solution` (JSON, never serialized) are separate columns, so leaking an answer would take a deliberate code change. `MATCH_PAIRS` has `solution = NULL`. |
| `lesson_attempts` | The integrity backbone. Each play-through has its own `status`, `mistakes` and `xp_awarded`, so XP is derived from server-observed answers. |
| `attempt_answers` | One row per exercise per attempt. The unique constraint on (`attempt_id`, `exercise_id`) makes retries idempotent and lets `/complete` count answered exercises. |
| `user_lesson_progress` | Marks the *first* completion of a lesson (unique per user+lesson). This drives state derivation and first-vs-practice XP, and records `best_mistakes`. |
| `user_skill_progress` | Records when a skill was unlocked (`unlocked_at`) and a `lessons_completed` counter. State itself is **derived**, not read from here (see Decisions). |
| `daily_activity` | One row per user per local date (unique). Accumulates `xp_earned` and `lessons_completed` for the daily goal and history. |
| `achievements` | Catalogue (code, title, description, icon), seeded from `seed.ACHIEVEMENTS`. |
| `user_achievements` | Unlocks. Unique (`user_id`, `achievement_id`) guarantees each unlocks at most once. |

All FK columns have `index=True`. `database._enable_sqlite_foreign_keys` turns on `PRAGMA foreign_keys=ON` for every SQLite connection.

---

## 3. Lesson-attempt integrity design (`backend/app/services/lesson_service.py`)

1. **`start_attempt`**
   - Computes lesson status via `lesson_meta` → `progress_service.lesson_status` and raises `403 LESSON_LOCKED` if the lesson is locked.
   - Applies `gamification.apply_heart_regen` and raises `409 OUT_OF_HEARTS` if the learner still has 0 hearts.
   - Inserts an `IN_PROGRESS` `LessonAttempt` and returns `AttemptStartOut`, whose exercises are `schemas.ExerciseOut` (`id`, `type`, `prompt`, `payload`). The schema has no `solution` field.
2. **`submit_answer`**
   - **Ownership:** a foreign or unknown attempt returns `404 ATTEMPT_NOT_FOUND`. An exercise from another lesson returns `400 EXERCISE_NOT_IN_LESSON`.
   - **Idempotency:** if `_stored_answer` finds a row, the service returns the stored `is_correct`/`note` and the current effective hearts. It does not grade again or charge again.
   - If the attempt is no longer `IN_PROGRESS`, it returns `409 ATTEMPT_NOT_IN_PROGRESS`.
   - **Wrong answer:** `attempt.mistakes += 1` and `gamification.lose_heart`, which regenerates first and floors at 0. At 0 hearts the attempt becomes `FAILED` and `out_of_hearts` is true.
   - **Concurrent duplicate:** if the insert hits the unique constraint (`IntegrityError`), the service rolls back and returns the winner's stored result. The heart deduction rolls back with it.
3. **`complete_attempt`**
   - A `COMPLETED` attempt goes to `_already_completed_summary` and awards nothing. A `FAILED` attempt returns `409 ATTEMPT_FAILED`.
   - If the count of `attempt_answers` doesn't equal the lesson's exercise count, it returns `409 INCOMPLETE_ATTEMPT`.
   - **Atomic claim:** `UPDATE lesson_attempts SET status='COMPLETED' WHERE id=:id AND status='IN_PROGRESS'`. If `rowcount != 1`, another request won, so it refreshes and returns the already-completed summary.
   - **Everything else happens in the same transaction**, followed by a single `db.commit()`:
     - `progress_service.record_lesson_completion` (lesson and skill progress, unlocks)
     - `gamification.lesson_xp`
     - the streak update (`next_streak`, `longest_streak`, `last_activity_date`)
     - the `DailyActivity` upsert
     - `user.xp`, `attempt.xp_awarded`
     - `gamification.award_achievements`

---

## 4. Lesson engine and renderer registry (frontend)

- **`components/lesson/LessonPlayer.tsx`** is an explicit `useReducer` state machine.
  - Phases: `LOADING`, `LOAD_ERROR`, `INTRO`, `STARTING`, `ANSWERING`, `CHECKING`, `FEEDBACK`, `SUBMITTING`, `COMPLETE`, `OUT_OF_HEARTS`.
  - Actions: `META_LOADED`, `START`, `STARTED`, `ANSWER_CHANGED`, `CHECK`, `CHECKED`, `NEXT`, `SUBMIT`, `COMPLETED`, `REFILLED`, plus the failure actions.
  - The player never auto-advances. `next()` moves on only from `FEEDBACK`, and routes to `OUT_OF_HEARTS` when `result.out_of_hearts`, to `submit()` on the last exercise, or to `NEXT` otherwise.
  - `ANSWER_CHANGED` is ignored outside `ANSWERING`, so input is locked while checking.
- **Keyboard.**
  - A window `keydown` listener (`useEffectEvent`) handles `Enter`: Check in `ANSWERING`, Continue in `FEEDBACK`, Start in `INTRO`.
  - Buttons outside `[data-exercise-area]` keep their native Enter. Inside the exercise area, Enter means Check even when an option button has focus.
  - `exercises/useNumberKeys.ts` maps `1`–`N` to options for `MultipleChoice` and `FillBlank`, and ignores keys typed into inputs.
- **`components/lesson/ExerciseRenderer.tsx`** holds `REGISTRY: { [T in ExerciseType]: ComponentType<ExerciseProps<T>> }`.
  - The mapped type makes TypeScript reject a missing type or a component with the wrong payload type. Adding a type means one component plus one registry entry (and the backend checker).
  - The component is rendered with `key={exercise.id}`, so each exercise mounts with fresh local state.
- **`exercises/types.ts → ExerciseProps<T>`.** Every exercise gets `exercise`, `disabled`, `status` (`idle`/`correct`/`incorrect`), `onAnswerChange(answer | null)` (null disables Check) and `onAutoSubmit(answer)`. `MatchPairs` uses `onAutoSubmit` when the last pair is matched.
- **Payload types.** `lib/types.ts` models `Exercise` as a discriminated union on `type`, and `ExerciseOf<T>` narrows it.

---

## 5. Client/server state split

| Server (source of truth) | Client (UI only) |
|---|---|
| XP, hearts + regen clock, gems, streak, daily goal, lesson/skill state, unlocks, achievements, attempt status, mistakes, correctness | Current exercise index, current selection/answer, last feedback result, word-bank placement, matched pairs, modal open/closed |

- **`context/UserStatsContext.tsx`** holds `/api/me` and exposes `refresh()`.
  - `LessonPlayer` calls `refresh()` after each answer (hearts) and after completion.
  - `OutOfHeartsModal` and `RightRail` refresh after a refill.
  - A timer re-reads `/api/me` when `me.next_heart_at` passes, so lazily regenerated hearts appear without a reload.
- **`lib/useApi.ts`** is a ~40-line fetch-on-mount hook returning `{data, error, loading, reload}` for page data (`/api/course`, `/api/profile`, `/api/leaderboard`).
- No Redux/Zustand and no client cache library.
- Hearts shown inside the lesson come from the server's `AnswerOut.hearts`, not from local arithmetic.

---

## 6. How FastAPI, Pydantic and SQLAlchemy are used

- **FastAPI**
  - Four `APIRouter`s with `/api` prefixes, and `response_model=` on every route.
  - Dependency injection covers the DB session (`database.get_db`), the user (`deps.get_current_user`) and the clock (`deps.get_now`). Tests swap all of these via `app.dependency_overrides`.
  - A `lifespan` context handles create-tables and auto-seed.
  - Exception handlers in `main.py` cover `AppError`, `RequestValidationError` (→ `422 VALIDATION_ERROR`, first error's location + message) and `StarletteHTTPException` (→ `NOT_FOUND` / `HTTP_<status>`).
  - An HTTP middleware converts anything else into `500 INTERNAL_ERROR` and logs it.
- **Pydantic v2**
  - `schemas.py` defines every request/response shape. `lib/types.ts` mirrors them by hand.
  - `UTCDateTime = Annotated[datetime, PlainSerializer(_utc_iso)]` serializes stored naive-UTC datetimes with an explicit `Z`.
  - `SkillState`/`LessonStatus` are `Literal` types.
  - `config.Settings` is a `pydantic_settings.BaseSettings` that reads env vars and `backend/.env`.
- **SQLAlchemy 2.x**
  - The typed declarative API (`Mapped[...]`, `mapped_column`) is used throughout, with `select()`-style queries.
  - `selectinload` eager-loads the course tree in `progress_service.get_course`.
  - Enums are stored as strings (`native_enum=False`).
  - Relationships carry `order_by` so `skill.lessons` and `lesson.exercises` come back ordered.
  - The atomic claim uses a Core `update()` with `synchronize_session=False`.
  - Engine events set the FK pragma and `BEGIN IMMEDIATE` (`database.serialize_sqlite_writes`).
  - `SessionLocal` uses `expire_on_commit=False` and `autoflush=False`.

---

## 7. Game rules (all enforced in `backend/app/services/`)

Constants live in `backend/app/config.py → Settings`, and each can be overridden by an env var of the same name.

| Rule | Implementation |
|---|---|
| **Hearts cap** | `MAX_HEARTS = 5` |
| **Wrong answer** | −1 heart, floored at 0, regen applied first (`gamification.lose_heart`). `mistakes += 1`. |
| **Match-pairs mismatch** | Costs nothing (checked client-side; the server only accepts `{completed: true}`). |
| **Duplicate answer** | Returns the stored result and costs no heart (unique `attempt_id, exercise_id`). |
| **0 hearts** | The attempt becomes `FAILED` and the response has `out_of_hearts: true`. `/start` returns `409 OUT_OF_HEARTS`. |
| **Lazy regen** | `regenerate_hearts`: `min(MAX, stored + floor(elapsed / HEART_REGEN_MINUTES))`. The clock advances only by consumed whole intervals. On reaching max, the clock resets to `now`. Applied on every read (`/api/me` via `effective_hearts`, which doesn't write) and before every deduction/refill. |
| **Regen clock start** | Losing a heart from full sets `hearts_updated_at = now` (`lose_heart`). `next_heart_at` is `null` at full hearts. |
| **Refill** | `refill_hearts`: `HEART_REFILL_GEM_COST = 350` gems → hearts = max. Otherwise `400 INSUFFICIENT_GEMS`, or `400 HEARTS_FULL` if already full. Gems are seeded at 500 and never earned. |
| **XP** | First completion: `BASE_LESSON_XP = 10` + `PERFECT_BONUS_XP = 5` if `mistakes == 0`. Replay: `PRACTICE_XP = 5` (`0` disables it). Implemented in `gamification.lesson_xp`. |
| **Completion guards** | Every exercise must be answered (`409 INCOMPLETE_ATTEMPT`). A `FAILED` attempt can't complete (`409 ATTEMPT_FAILED`). A `COMPLETED` attempt returns the stored summary with `already_completed: true`. |
| **Streak** (on completion only) | `next_streak`: last == today → unchanged; last == today−1 → +1; otherwise → 1. `longest_streak = max(...)`. |
| **Streak display** | `display_streak`: if `last_activity_date < today − 1` (or none), show 0. There is no cron. |
| **"Today"** | `clock.local_date(now)`, the calendar date in `APP_TIMEZONE` (default `Asia/Kolkata`). |
| **Daily goal** | `daily_activity` is unique on (user, date) and accumulates `xp_earned`. Met when `earned >= daily_goal_xp` (`DEFAULT_DAILY_GOAL_XP = 20`). `daily_goal_just_met(before, after, goal)` is `before < goal <= after`, so it fires exactly once. |
| **Skill states** | `derive_skill_views`: `LOCKED` (previous skill not `COMPLETED`), `AVAILABLE` (0 done), `IN_PROGRESS` (0 < done < total), `COMPLETED` (done == total). The first skill by course-wide `order_index` is always unlocked. |
| **Lesson states** | `COMPLETED` if in `user_lesson_progress`. `AVAILABLE` if the skill is unlocked and the previous lesson is done. Otherwise `LOCKED`. |
| **Progress %** | `round(100 * done / total)`. Replays don't double-count, because `user_lesson_progress` is unique per lesson. |
| **Unlock event** | `record_lesson_completion` diffs skill views before/after and reports the first skill that went from `LOCKED` to unlocked as `newly_unlocked_skill`. |
| **Achievements** | `earned_achievement_codes`: `FIRST_LESSON` ≥1 distinct lesson · `PERFECT_LESSON` this completion had 0 mistakes · `XP_100` total XP ≥ 100 · `STREAK_3` streak ≥ 3 · `LESSONS_5` ≥5 *distinct* lessons. `award_achievements` skips owned ones, and the unique constraint backs it up. |
| **Answer checking** | `normalize`: NFC → lowercase → strip `.,!?¿¡` → collapse whitespace → trim. `MULTIPLE_CHOICE`/`FILL_BLANK` use exact normalized equality with no accent tolerance. `WORD_BANK` (tiles joined by spaces, order matters) and `TYPE_ANSWER` go through `match_text` against all `accepted` answers. An accent-only difference is correct with `note: "Watch your accents: <matched option>"`. |

---

## 8. Decisions (with alternatives considered)

1. **Lesson attempts as the integrity backbone.**
   - The server computes XP from `lesson_attempts.mistakes`.
   - `UniqueConstraint("attempt_id", "exercise_id")` on `attempt_answers` makes answer retries idempotent.
   - The conditional `update(LessonAttempt).where(status == IN_PROGRESS)` in `lesson_service.complete_attempt` claims completion atomically, so a double-click can't award XP twice.
   - *Alternatives:* a client-reported score (trivially spoofable). A per-lesson "completed" flag with no attempt record (no mistake tracking, no idempotency, no way to reject completing an unanswered lesson).
2. **Skill/lesson state is derived, not stored.**
   - `progress_service.derive_skill_views` computes every state from the set of `user_lesson_progress` lesson IDs on every read. It is a pure function and is unit-tested.
   - `user_skill_progress` rows are kept only for `unlocked_at`/`lessons_completed` history.
   - *Alternative:* stored state enums updated on completion, which can drift from the underlying progress (partial writes, content changes).
3. **Lazy heart regeneration.**
   - `gamification.regenerate_hearts` advances `hearts_updated_at` by whole intervals only, which keeps partial progress toward the next heart.
   - *Alternative:* a cron/background job ticking hearts. That means more infrastructure, drift between ticks and work for idle users.
4. **SQLite `BEGIN IMMEDIATE`** (`database.serialize_sqlite_writes`).
   - The game-rules audit found that parallel wrong answers could each read `hearts=5` and write 4 (lost deductions). Taking the write lock at `BEGIN` serializes the read-modify-write.
   - Verified live in the main session: 3 parallel wrong answers cost exactly 3 hearts. `test_serialize_sqlite_writes_takes_the_write_lock_at_begin` covers the hook.
   - *Alternatives:* an optimistic `version_id_col` with retry. `SELECT … FOR UPDATE` on PostgreSQL in production.
5. **Replay summary is recomputed, not stored.**
   - A `/complete` on a `COMPLETED` attempt (`_already_completed_summary`) returns the stored `xp_awarded` and mistakes plus current state, with neutral event fields: `extended=false`, `just_met=false`, `newly_unlocked_skill=null`, `new_achievements=[]`.
   - *Alternative:* persisting the original summary as JSON. Rejected because the spec forbids JSON columns for user state.
6. **Injected clock and naive UTC.**
   - `now` comes from `deps.get_now`, so tests freeze time with `dependency_overrides[get_now]` (`conftest.FrozenClock`).
   - "Today" is `clock.local_date(now)` in `APP_TIMEZONE`.
   - Datetimes are stored naive UTC because SQLite drops tzinfo. `schemas.UTCDateTime` adds the `Z` on output.
   - *Alternatives:* `datetime.now()` inside rules (untestable), or aware datetimes in SQLite (silently become naive and mix badly).
7. **Match pairs validated client-side.**
   - This gives instant per-tap feedback, and a mismatch costs no heart. The server accepts `{completed: true}` (`answer_check.check_answer`).
   - *Trade-off:* spoofable, but it can't award XP on its own or skip the other exercises.
   - *Alternative:* sending every tap to the server, or submitting the full pairing. That is slower and needs a pairing solution, which the payload already reveals anyway.
8. **Error middleware inside CORS.**
   - `unhandled_error_middleware` is registered before `CORSMiddleware`, so CORS is outermost and 500s carry `Access-Control-Allow-Origin` and the standard error body. This was an audit finding: Starlette's default 500 handler sits outside CORS, so browsers saw an opaque network error.
   - *Alternative:* a generic `@app.exception_handler(Exception)`, which runs in Starlette's outermost `ServerErrorMiddleware`, outside CORS.
9. **NFC normalization.**
   - `answer_check.normalize` applies `unicodedata.normalize("NFC", …)` first. The test suite showed that decomposed accents (`o` + U+0301) were flagged as accent mistakes. `test_decomposed_unicode_accents_count_as_exact` covers this.
   - *Alternative:* NFD everywhere, which would complicate the accent-note comparison.
10. **Frontend state and rendering.**
    - No Redux: `UserStatsContext` plus the tiny `lib/useApi` hook.
    - `LessonPlayer` is an explicit `useReducer` state machine.
    - The `ExerciseRenderer` registry is typed as `{[T in ExerciseType]: ComponentType<ExerciseProps<T>>}`.
    - A deterministic seeded shuffle (`lib/shuffle.ts`, mulberry32 seeded by `exercise.id`) keeps `MatchPairs` rendering pure and stable across re-renders.
    - Enter inside `[data-exercise-area]` means Check even when an option button has focus (found in browser testing).
    - *Alternatives:* Redux/Zustand (overkill for one `/api/me` object), a `switch` in JSX (no compile-time exhaustiveness per payload type), `Math.random()` in render (impure, reshuffles on re-render).
11. **Next.js 16 specifics.**
    - Route `params` is a Promise (`app/lesson/[id]/page.tsx` awaits it).
    - Tailwind v4 design tokens live in `app/globals.css` `@theme`, with no `tailwind.config`.
    - An SVG Spanish flag (`components/ui/CourseFlag.tsx`) is used because Windows can't render flag emoji.
    - `turbopack.root` is pinned in `next.config.ts` so a stray lockfile higher up the filesystem isn't picked as the workspace root.
12. **Project subagents** (`.claude/agents/`: `spanish-content-reviewer`, `game-rules-auditor`, `verifier`, `docs-writer`) were used for review and verification, while the main session did all building. Their findings were fixed in the `phase-3` commit:
    - ambiguous fill-blank options (one grammatical blank per sentence)
    - extra accepted answers
    - the heart race
    - CORS on 500s
    - NFC normalization

---

## 9. Security and integrity

- **Why the server owns XP, hearts and streak.** Anything computed on the client can be edited in DevTools. The client never sends XP, hearts, streak, progress or unlocks. It sends answers, and the server decides correctness, deductions and rewards inside a transaction.
- **Solutions never leave the server.**
  - `schemas.ExerciseOut` has no `solution` field, so FastAPI's `response_model` filtering drops it.
  - `test_start_creates_attempt_and_hides_solutions` and `test_type_answer_solutions_never_leak_in_start` guard this, and the smoke test asserts it against the live server.
  - `correct_answer` is revealed only *after* an answer is stored for that exercise.
- **Match-pairs trade-off.** The pairs are in the `payload` (the client needs them to render), so validating on the client reveals nothing new. A forged `{completed: true}` only skips one exercise's feedback. It can't award XP, because completion still requires every other exercise to be answered through the server.
- **Still spoofable without auth.**
  - Anyone who can reach the API can act as the seeded learner. `deps.get_current_user` is the single seam where real auth would go.
  - Answers can be learned by answering wrong, because `correct_answer` is returned. That costs hearts, and the next attempt can then be "perfect".
  - Match pairs can be auto-completed.
  - There is no rate limiting.
- **CORS** is restricted to `CORS_ORIGINS`, with methods `GET`/`POST` and header `Content-Type` only. `test_cors_rejects_unknown_origins` covers it.
- **Errors never leak stack traces.** Every error goes through `_error()` in `main.py` as `{"detail": {"code", "message"}}`, and unexpected exceptions are logged server-side only.
- **Ownership checks.** `_get_attempt` returns 404 for another user's attempt, and exercises must belong to the attempt's lesson.

---

## 10. Testing

- **pytest.** `backend/tests/` has 167 tests, all passing (count taken from a fresh-clone run). They use in-memory SQLite (`sqlite://` + `StaticPool` + `check_same_thread=False`) and a frozen clock (`FIXED_NOW = 2026-01-15 06:30 UTC`, which is noon in Kolkata).
  - `conftest.py` pins every env var *before* importing `app`, so a demo `backend/.env` can't change the rules under test.
  - It overrides `get_db` and `get_now` and never enters the TestClient context manager, so the lifespan auto-seed never runs.
  - `test_answer_check.py` covers normalize, accent notes, multiple accepted answers, word-bank order, decomposed Unicode and invalid payloads.
  - `test_gamification.py` covers regen (partial progress, cap, clock reset), `lose_heart` floor, refill with, without and with exact gems, streak cases, `display_streak`, XP, `just_met` and achievement codes/awarding.
  - `test_lesson_flow.py` covers the API end to end:
    - hidden solutions and locked/0-heart guards
    - regen before the zero check
    - duplicate answers and running out of hearts
    - base/perfect/practice XP and completion idempotency
    - unanswered completion and daily-goal crossing once
    - timezone-day streaks, broken-streak display and each achievement unlocking once
  - `test_progress.py` covers state derivation, sequential unlocking, progress rounding, no double-counting on replay and the course tree.
  - `test_seed.py` covers the §7 invariants (structure, 5–7 exercises with ≥3 types, Unit 1 has every type, learner stats/activity/achievements, rivals, dates relative to `now`) and CLI idempotency.
  - `test_api_misc.py` covers `/api/me` regen-on-read, refill, profile, leaderboard, achievements, the error format (404/405/422/500), CORS, the `BEGIN IMMEDIATE` hook and the clock override.
- **Smoke test.** `backend/scripts/smoke_test.py` makes 22 checks against the live server on a fresh seed:
  - health, the seeded state and `403 LESSON_LOCKED`
  - no solutions in `/start`
  - wrong answer → 4 hearts, and a duplicate submission doesn't charge again
  - `409 INCOMPLETE_ATTEMPT`
  - +10 XP → 55 total, streak 3→4, and Introductions COMPLETED with Common Words unlocked
  - an idempotent second `/complete`
  - persisted `/api/me` and `/api/course`
- **Frontend.** `npx tsc --noEmit`, `npm run lint` and `npm run build` are clean. A Playwright journey against the production build (run in the main session) passed 46 checks, including:
  - the heart loss, a full lesson, streak 3→4 and the unlock
  - hard-refresh persistence
  - the out-of-hearts modal and refill
  - a perfect lesson (+15 XP, Flawless toast) and a practice replay (+5 XP)
  - `just_met` once, and the secondary pages
  - no overflow at 375px and zero console errors

---

## 11. Production path

- **PostgreSQL + Alembic.** Replace `create_all` with migrations. `database.py` currently passes SQLite-only `connect_args` and installs the `BEGIN IMMEDIATE` hook only for the SQLite dialect. On Postgres, use `SELECT … FOR UPDATE` on the user row (or optimistic versioning) for the read-modify-write in answer/complete.
- **Auth (JWT/OAuth).** Replace `deps.get_current_user` with token verification. Every user-scoped query already gets the user from that dependency, so nothing else changes. Add rate limiting on `/answer`.
- **Leaderboard.** Use a Redis sorted set (`ZINCRBY` on XP award, `ZREVRANGE`/`ZREVRANK` to read) with weekly keys for leagues, instead of `ORDER BY xp` over all users.
- **Background jobs.** Hearts and streaks stay lazy. Jobs would handle streak-reminder notifications, weekly league rollover and analytics, via a queue (e.g. Celery/RQ/Cloud Tasks).
- **Media.** Use object storage + a CDN for audio and images (listening/speaking exercises), with URLs in exercise `payload`.
- **Containerized deploy.** Build separate images for the API (uvicorn/gunicorn workers) and the Next.js app. Use managed Postgres and Redis, with config via the same env vars `Settings` already reads.
- **Content.** Move course content out of `seed.py` into an authoring pipeline or admin tool.

---

## 12. Likely interview questions

1. **How do you stop a user from giving themselves XP?** The client never sends XP. `lesson_service.complete_attempt` computes it from the attempt's server-recorded `mistakes` and whether `user_lesson_progress` already had the lesson (`gamification.lesson_xp`).

2. **What if the user double-clicks Complete?** The conditional `UPDATE … WHERE status='IN_PROGRESS'` lets exactly one request claim the attempt. The other sees `rowcount != 1` and gets `_already_completed_summary` with `already_completed: true` and nothing awarded.

3. **What if they resubmit an answer to avoid losing a heart, or retry after a timeout?** `attempt_answers` is unique on (`attempt_id`, `exercise_id`). `submit_answer` returns the stored result without charging again. A concurrent duplicate hits `IntegrityError`, rolls back and returns the winner's result.

4. **How do hearts regenerate without a cron job?** Lazily. `regenerate_hearts` computes `min(MAX, stored + floor(elapsed/interval))` whenever hearts are read or changed. It advances `hearts_updated_at` by whole intervals only, so partial progress isn't lost.

5. **Why does `/api/me` not write regenerated hearts back?** It doesn't need to. `effective_hearts` is a pure computation from stored hearts and the stored clock. Writes happen only when state changes (deduction, refill, start), which keeps GETs side-effect free.

6. **How is the streak computed, and how does it break?** On completion, `next_streak` keeps it (same day), increments it (yesterday) or resets it to 1. Nothing runs at midnight. `display_streak` shows 0 when the last activity is before yesterday, and the next completion resets it to 1.

7. **What does "today" mean?** `clock.local_date(now)`: the calendar date in `APP_TIMEZONE`. A test (`test_streak_follows_the_app_timezone_day`) checks that the day boundary follows Kolkata, not UTC.

8. **How do you test time-dependent rules?** Rules take `now`/`today` as parameters. The API gets `now` from `deps.get_now`, which the tests override with `FrozenClock` and advance explicitly.

9. **Why is skill state derived instead of stored?** `derive_skill_views` is a pure function of completed lesson IDs, so state can't drift from progress. Stored enums would need to be updated correctly on every write path forever.

10. **How does unlocking work across units?** `skills.order_index` is unique course-wide. `ordered_skills` flattens units and sorts by it, and each skill is unlocked iff the previous one is `COMPLETED`.

11. **How do you know which skill was just unlocked?** `record_lesson_completion` derives views before and after adding the lesson and returns the first skill that changed from `LOCKED`.

12. **How does `just_met` fire only once?** `daily_goal_just_met(before, after, goal)` is `before < goal <= after`, computed from today's `daily_activity.xp_earned` before and after adding this lesson's XP. The next lesson starts above the goal, so it's false.

13. **How do achievements unlock only once?** `award_achievements` filters out codes the user already owns, and `unique(user_id, achievement_id)` is the DB-level backstop. It all runs in the completion transaction, so a failure rolls back XP and achievements together.

14. **Why is match pairs validated on the client?** Instant per-tap feedback, and the pairs are already in the payload (there's nothing secret to protect). A mismatch costs no heart. The server accepts `{completed: true}`. Forging it skips one exercise but can't award XP by itself.

15. **How do you guarantee solutions never leak?** They live in a separate `solution` column that is never mapped onto a response schema. `ExerciseOut` has only `id/type/prompt/payload`, and tests plus the smoke test assert it.

16. **How does accent-tolerant checking work?** `match_text` first compares `normalize()`d strings against every accepted answer. If none match, it compares with accents stripped (`strip_accents`, NFD minus combining marks). An accent-only match is correct with `note: "Watch your accents: …"`. Multiple choice and fill-blank are exact.

17. **What race condition did you find, and how did you fix it?** Parallel wrong answers each read `hearts=5` and each wrote 4. The fix is `database.serialize_sqlite_writes`, which disables pysqlite's implicit BEGIN and issues `BEGIN IMMEDIATE`, so the write lock is taken before the first read. On Postgres you would use `SELECT … FOR UPDATE`.

18. **Why SQLite?** Zero setup, a single file, and it's enough for a single-user demo. Its limits (write concurrency, tz-naive datetimes, FKs off by default) are handled explicitly. Postgres + Alembic is the production path.

19. **How is the error format kept consistent?** `AppError(status, code, message)` is raised by services, and `main.py` has handlers for `AppError`, validation errors and HTTP exceptions, plus a middleware for unexpected exceptions. They all go through `_error()`. On the client, `lib/api.ts` parses `detail.code` into `ApiError`, and `isApiError(err, "OUT_OF_HEARTS")` drives UI branches.

20. **Why does the 500 handler sit in a middleware?** A plain `Exception` handler runs in Starlette's outermost `ServerErrorMiddleware`, outside CORS, so the browser saw a CORS failure instead of the JSON error. The middleware is registered before `CORSMiddleware`, which places it inside.

21. **How does the lesson player avoid inconsistent UI states?** It's a reducer with explicit phases. Actions are ignored in the wrong phase (e.g. `ANSWER_CHANGED` outside `ANSWERING`), it never auto-advances, and buttons disable during `CHECKING`/`SUBMITTING`.

22. **How would you add a sixth exercise type?** Add the enum value in `models.ExerciseType`, a branch in `answer_check.check_answer`, a seed builder, the payload type in `lib/types.ts`, one component, and one `REGISTRY` entry. The mapped registry type makes the compiler flag a missing entry.

23. **How does the frontend know hearts changed?** Answer responses include `hearts`, and the player shows that value. It also calls `UserStatsContext.refresh()`. The context schedules a re-read at `next_heart_at`, so regenerated hearts appear without a reload.

24. **Why no Redux?** The only shared server state is one `/api/me` object. Context plus `refresh()` covers it, and per-page data uses `useApi`. The spec also forbids Redux/Zustand.

25. **What's still insecure?** There is no auth: anyone can act as the seeded learner. Answers can be learned by answering wrong (costs hearts), match pairs can be auto-completed, and there is no rate limiting. Auth slots into `deps.get_current_user`.

26. **How would you scale the leaderboard?** Use a Redis sorted set updated in the completion transaction's after-commit hook, with weekly keys for leagues and `ZREVRANK` for "your rank". Today it's `ORDER BY xp DESC, id` over `users`, which is fine for six rows.

27. **How is the demo kept repeatable?** `python -m app.seed --reset` drops and recreates all tables, then seeds dates relative to "today" in `APP_TIMEZONE`, so the streak is always 3 ending yesterday. `test_seed_cli_is_idempotent` and `test_seed_cli_reset_rebuilds_the_same_data` guard it. `AUTO_SEED` also seeds an empty DB on startup.

28. **How does the seeded history stay consistent with the achievements?**
    - Arnav's three completed lessons each have `best_mistakes=1`, so `PERFECT_LESSON` stays locked.
    - 45 XP = three first completions (10 each) + three practice replays (5 each), spread as 15 XP/day over the previous 3 days.
    - `FIRST_LESSON` and `STREAK_3` are unlocked.
