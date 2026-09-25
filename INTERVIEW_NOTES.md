# Duolingo (assessment build): Interview Notes

These notes are written from the code as it stands. Paths are relative to the repo root. The product is branded "Duolingo" at the user's request (see Decision 17). The mascot, Pico, and all artwork are original.

---

## 1. Architecture and data flow

```text
Browser (Next.js 16 App Router, React 19, TS strict, Tailwind v4)
  app/(main)/page.tsx ─ useApi(api.course, activeCourseId) ─┐
  context/UserStatsContext.tsx ─ api.me() / replace(me) ────┤  lib/api.ts  request<T>()
  components/lesson/LessonPlayer.tsx (lesson + practice) ───┤  → fetch(NEXT_PUBLIC_API_URL + path)
  components/settings/* ─ api.updateSettings / setCourse ───┤  → ApiError(status, code, message)
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

content/  spanish · french · punjabi · english  ──validate_course──▶ seed.py
```

**A typical request.** Take `POST /api/attempts/{id}/answer`:

1. `routers/lessons.py:answer_exercise` validates the body as `schemas.AnswerIn` (`exercise_id`, `answer` dict).
2. It resolves the session, the learner and `now` through dependencies, then calls `lesson_service.submit_answer`.
3. The service loads the attempt and checks that it belongs to the user and that the exercise belongs to the attempt's lesson.
4. It returns the stored result if this exercise was already answered. Otherwise it grades with `answer_check.check_answer`, applies heart regen and (in `LESSON` mode only) any deduction, inserts an `AttemptAnswer` and commits.
5. The router returns `schemas.AnswerOut`.

**Layering rule.** Routers are thin (parse, call a service, return a schema). All rules live in `services/`. Rule functions take `now`/`today` as parameters. The only clock reads are `clock.utc_now()`, called through `deps.get_now`, and the seed's default `now` when run from the CLI. `POST /api/me/reset` passes the injected `now` into `seed.restore_demo`, so a demo restore is testable with the frozen clock.

**Startup.** The `lifespan` hook in `main.py` runs `Base.metadata.create_all(engine)`. If `settings.AUTO_SEED` is set and `seed.is_seeded()` is false, it runs `seed.seed()`, so an empty DB on a fresh host becomes a working demo.

**Multiple courses.** `content/__init__.py` exports `COURSES = [SPANISH, FRENCH, PUNJABI, ENGLISH]`. `seed.seed` inserts each through `_add_course`, which calls `builders.validate_course` first. The learner's current course is `users.active_course_id`. `progress_service.active_course` resolves it (falling back to the first course), and every course-scoped read (`/api/course`, `/api/profile`, `/api/practice/start`, the course reset) goes through it. Lesson endpoints work on any lesson ID: `lesson_status` resolves the lesson's own course with `course_of_lesson`, so a lesson from a non-active course still follows that course's unlock rules.

---

## 2. Tables and why each exists (`backend/app/models.py`)

| Table | Why it exists |
|---|---|
| `users` | Holds all learner state as typed columns. `hearts` + `hearts_updated_at` drive lazy regen. `last_activity_date` drives the streak. `daily_goal_xp` is per-user. `active_course_id` (nullable FK) selects the course. The settings (`display_name`, `avatar_color`, `sound_effects`, `daily_reminder`, `achievement_alerts`) are plain columns, not a JSON blob. |
| `courses` → `units` → `skills` → `lessons` → `exercises` | Content hierarchy with `order_index` at every level. `courses.language_code` is unique and `courses.description` feeds the course switcher. `skills.order_index` runs across units within a course and restarts at 1 per course, so unlocking is a single ordered walk. It is indexed but not DB-unique, because `skills` has no `course_id` column; `seed._add_course` assigns it. |
| `exercises` | `payload` (JSON, safe to send) and `solution` (JSON, never serialized) are separate columns, so leaking an answer would take a deliberate code change. `MATCH_PAIRS` has `solution = NULL`. |
| `lesson_attempts` | The integrity backbone. Each play-through has its own `status`, `mode` (`LESSON` or `PRACTICE`), `mistakes` and `xp_awarded`, so XP is derived from server-observed answers. Completed `LESSON` attempts are also the permanent record of "has this learner ever finished this lesson", which survives a course reset. |
| `attempt_answers` | One row per exercise per attempt. The unique constraint on (`attempt_id`, `exercise_id`) makes retries idempotent and lets `/complete` count answered exercises. |
| `user_lesson_progress` | Marks the *current* completion of a lesson (unique per user+lesson). This drives state derivation and records `best_mistakes`, which heart practice uses to pick the weakest lesson. A course reset deletes these rows. |
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
   - `_create_attempt` inserts an `IN_PROGRESS` `LessonAttempt` (`mode=LESSON`) and returns `AttemptStartOut`, whose exercises are `schemas.ExerciseOut` (`id`, `type`, `prompt`, `payload`). The schema has no `solution` field.
2. **`start_practice`** (heart practice)
   - Picks the weakest completed lesson in the active course: most `best_mistakes` first, then the one completed longest ago. With no completions it uses the course's first lesson, which is always unlocked.
   - It has no hearts check, so it works at 0 hearts. It applies regen and creates a `mode=PRACTICE` attempt.
3. **`submit_answer`**
   - **Ownership:** a foreign or unknown attempt returns `404 ATTEMPT_NOT_FOUND`. An exercise from another lesson returns `400 EXERCISE_NOT_IN_LESSON`.
   - **Idempotency:** if `_stored_answer` finds a row, the service returns the stored `is_correct`/`note` and the current effective hearts. It does not grade again or charge again.
   - If the attempt is no longer `IN_PROGRESS`, it returns `409 ATTEMPT_NOT_IN_PROGRESS`.
   - **Wrong answer:** `attempt.mistakes += 1`. Only in `LESSON` mode does it also call `gamification.lose_heart` (regenerates first, floors at 0); at 0 hearts the attempt becomes `FAILED` and `out_of_hearts` is true. A `PRACTICE` attempt never costs a heart and never fails.
   - **Concurrent duplicate:** if the insert hits the unique constraint (`IntegrityError`), the service rolls back and returns the winner's stored result. The heart deduction rolls back with it.
4. **`complete_attempt`**
   - A `COMPLETED` attempt goes to `_neutral_summary(already_completed=True)` and awards nothing. A `FAILED` attempt returns `409 ATTEMPT_FAILED`.
   - For `LESSON` mode it re-checks `lesson_status` and returns `409 LESSON_LOCKED` if a course reset locked the lesson after the attempt started.
   - If the count of `attempt_answers` doesn't equal the lesson's exercise count, it returns `409 INCOMPLETE_ATTEMPT`.
   - **Atomic claim:** `UPDATE lesson_attempts SET status='COMPLETED' WHERE id=:id AND status='IN_PROGRESS'`. If `rowcount != 1`, another request won, so it refreshes and returns the already-completed summary.
   - **Practice branch:** applies regen, adds one heart if below `MAX_HEARTS`, sets `xp_awarded = 0`, commits and returns `_neutral_summary(hearts_restored=0|1)`. No XP, streak, daily goal, progress or achievements change.
   - **Lesson branch: everything else happens in the same transaction**, followed by a single `db.commit()`:
     - `progress_service.record_lesson_completion` (lesson and skill progress, unlocks)
     - `completed_before(db, user, lesson.id, exclude_attempt_id=attempt.id)`, so a lesson finished before a course reset pays practice XP
     - `gamification.lesson_xp`
     - the streak update (`next_streak`, `longest_streak`, `last_activity_date`)
     - the `DailyActivity` upsert
     - `user.xp`, `attempt.xp_awarded`
     - `gamification.award_achievements`

---

## 4. Lesson engine and renderer registry (frontend)

- **`components/lesson/LessonPlayer.tsx`** is an explicit `useReducer` state machine used by both `/lesson/[id]` and `/practice` (`<LessonPlayer practice />`).
  - Phases: `LOADING`, `LOAD_ERROR`, `INTRO`, `STARTING`, `ANSWERING`, `CHECKING`, `FEEDBACK`, `SUBMITTING`, `COMPLETE`, `OUT_OF_HEARTS`.
  - Actions: `META_LOADED`, `START`, `STARTED`, `ANSWER_CHANGED`, `CHECK`, `CHECKED`, `NEXT`, `SUBMIT`, `COMPLETED`, `REFILLED`, `OUT_OF_HEARTS`, plus the failure actions.
  - In practice mode there's no lesson to preview, so the player starts in `INTRO` and calls `api.startPractice()`; the server chooses the lesson.
  - The player never auto-advances. `next()` moves on only from `FEEDBACK`, and routes to `OUT_OF_HEARTS` when `result.out_of_hearts`, to `submit()` on the last exercise, or to `NEXT` otherwise.
  - `ANSWER_CHANGED` is ignored outside `ANSWERING`, so input is locked while checking.
  - Sound effects come from `lib/sound.ts → playSound(name, enabled)`, gated on `me.settings.sound_effects`. Achievement toasts on `LessonComplete` are gated on `me.settings.achievement_alerts`.
- **Keyboard.**
  - A window `keydown` listener (`useEffectEvent`) handles `Enter`: Check in `ANSWERING`, Continue in `FEEDBACK`, Start in `INTRO`.
  - Buttons outside `[data-exercise-area]` keep their native Enter. Inside the exercise area, Enter means Check even when an option button has focus.
  - `exercises/useNumberKeys.ts` maps `1`–`N` to options for `MultipleChoice` and `FillBlank`, and ignores keys typed into inputs.
- **`components/lesson/ExerciseRenderer.tsx`** holds `REGISTRY: { [T in ExerciseType]: ComponentType<ExerciseProps<T>> }`.
  - The mapped type makes TypeScript reject a missing type or a component with the wrong payload type. Adding a type means one component plus one registry entry (and the backend checker).
  - The component is rendered with `key={exercise.id}`, so each exercise mounts with fresh local state.
- **`exercises/types.ts → ExerciseProps<T>`.** Every exercise gets `exercise`, `language` (`LessonLanguage {code, name}`), `disabled`, `status` (`idle`/`correct`/`incorrect`), `onAnswerChange(answer | null)` (null disables Check) and `onAutoSubmit(answer)`. `MatchPairs` uses `onAutoSubmit` when the last pair is matched. `TypeAnswer` uses `language` for the input's `lang` attribute, its label and placeholder, and the accented-letter buttons (`SPECIAL_CHARACTERS` has entries for `es` and `fr`).
- **Payload types.** `lib/types.ts` models `Exercise` as a discriminated union on `type`, and `ExerciseOf<T>` narrows it.

---

## 5. Client/server state split

| Server (source of truth) | Client (UI only) |
|---|---|
| XP, hearts + regen clock, gems, streak, daily goal, lesson/skill state, unlocks, achievements, attempt status and mode, mistakes, correctness, active course, profile settings, sound/reminder/alert preferences | Current exercise index, current selection/answer, last feedback result, word-bank placement, matched pairs, modal open/closed, the **theme** (per device, `localStorage`), and the "reminder already sent today" marker |

- **`context/UserStatsContext.tsx`** holds `/api/me` and exposes `refresh()` and `replace(me)`.
  - `LessonPlayer` calls `refresh()` after each answer (hearts) and after completion.
  - `OutOfHeartsModal` and `RightRail` refresh after a refill.
  - `PATCH /api/me/settings` and `POST /api/me/course` return the full `MeOut`, so `useSettingsSave`, `CourseSwitcher` and the Settings language section call `replace()` with it instead of making a second request.
  - A timer re-reads `/api/me` when `me.next_heart_at` passes, so lazily regenerated hearts appear without a reload.
- **`components/settings/useSettingsSave.ts`** keeps an optimistic overlay per field: the control shows the new value at once, the server's `Me` replaces the cache on success, and the overlay is dropped (reverting the control) on failure, with a per-field error.
- **`lib/useApi.ts`** is a small fetch-on-mount hook returning `{data, error, loading, reload}` for page data. It takes a `key`, and the home page passes `me.active_course.id`, so switching course refetches `/api/course`.
- **Theme** (`lib/theme.ts`): `useTheme()` reads `localStorage` through `useSyncExternalStore`. `THEME_INIT_SCRIPT` runs inline in `<head>` (in `app/layout.tsx`) and sets `data-theme` before first paint.
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
  - `CORSMiddleware` allows `GET`, `POST` and `PATCH` with the `Content-Type` header.
- **Pydantic v2**
  - `schemas.py` defines every request/response shape. `lib/types.ts` mirrors them by hand.
  - `SettingsIn` is a partial-update model: every field is optional, `display_name` has `min_length=1, max_length=30` and a `field_validator` that strips whitespace, `avatar_color` has a `#RRGGBB` pattern, and `daily_goal_xp` must be in `DAILY_GOAL_CHOICES = (10, 20, 30, 50)`. The router applies `model_dump(exclude_unset=True)` and skips `None` values. Unknown keys are ignored (Pydantic's default).
  - `ResetIn.scope` is `Literal["course", "demo"]`.
  - `UTCDateTime = Annotated[datetime, PlainSerializer(_utc_iso)]` serializes stored naive-UTC datetimes with an explicit `Z`.
  - `SkillState`/`LessonStatus` are `Literal` types.
  - `config.Settings` is a `pydantic_settings.BaseSettings` that reads env vars and `backend/.env`.
- **SQLAlchemy 2.x**
  - The typed declarative API (`Mapped[...]`, `mapped_column`) is used throughout, with `select()`-style queries.
  - `selectinload` eager-loads the course tree (`progress_service._course_query`).
  - Enums (`ExerciseType`, `AttemptStatus`, `AttemptMode`) are stored as strings (`native_enum=False`).
  - Relationships carry `order_by` so `skill.lessons` and `lesson.exercises` come back ordered.
  - The atomic claim and the course reset use Core `update()`/`delete()` with `synchronize_session=False`. `completed_before` is an `exists()` subquery.
  - Engine events set the FK pragma and `BEGIN IMMEDIATE` (`database.serialize_sqlite_writes`).
  - `SessionLocal` uses `expire_on_commit=False` and `autoflush=False`.

---

## 7. Game rules (all enforced in `backend/app/services/`)

Constants live in `backend/app/config.py → Settings`, and each can be overridden by an env var of the same name.

| Rule | Implementation |
|---|---|
| **Hearts cap** | `MAX_HEARTS = 5` |
| **Wrong answer** | In a `LESSON` attempt: −1 heart, floored at 0, regen applied first (`gamification.lose_heart`). `mistakes += 1` in both modes. |
| **Match-pairs mismatch** | Costs nothing (checked client-side; the server only accepts `{completed: true}`). |
| **Duplicate answer** | Returns the stored result and costs no heart (unique `attempt_id, exercise_id`). |
| **0 hearts** | The attempt becomes `FAILED` and the response has `out_of_hearts: true`. `/start` returns `409 OUT_OF_HEARTS`. `/api/practice/start` still works. |
| **Lazy regen** | `regenerate_hearts`: `min(MAX, stored + floor(elapsed / HEART_REGEN_MINUTES))`. The clock advances only by consumed whole intervals. On reaching max, the clock resets to `now`. Applied on every read (`/api/me` via `effective_hearts`, which doesn't write) and before every deduction/refill. |
| **Regen clock start** | Losing a heart from full sets `hearts_updated_at = now` (`lose_heart`). `next_heart_at` is `null` at full hearts. |
| **Refill** | `refill_hearts`: `HEART_REFILL_GEM_COST = 350` gems → hearts = max. Otherwise `400 INSUFFICIENT_GEMS`, or `400 HEARTS_FULL` if already full. Gems are seeded at 500 and never earned. |
| **Heart practice** | `start_practice` needs no hearts. Mistakes are free. Completing restores 1 heart (only if below max, after regen) and awards 0 XP. No streak, daily goal, progress or achievement changes. |
| **XP** | First completion: `BASE_LESSON_XP = 10` + `PERFECT_BONUS_XP = 5` if `mistakes == 0`. Replay: `PRACTICE_XP = 5` (`0` disables it). Implemented in `gamification.lesson_xp`. "First" means no `user_lesson_progress` row **and** no earlier completed `LESSON` attempt (`completed_before`). |
| **Completion guards** | Every exercise must be answered (`409 INCOMPLETE_ATTEMPT`). A `FAILED` attempt can't complete (`409 ATTEMPT_FAILED`). A lesson re-locked by a reset can't complete (`409 LESSON_LOCKED`). A `COMPLETED` attempt returns the stored summary with `already_completed: true`. |
| **Streak** (on lesson completion only) | `next_streak`: last == today → unchanged; last == today−1 → +1; otherwise → 1. `longest_streak = max(...)`. |
| **Streak display** | `display_streak`: if `last_activity_date < today − 1` (or none), show 0. There is no cron. |
| **"Today"** | `clock.local_date(now)`, the calendar date in `APP_TIMEZONE` (default `Asia/Kolkata`). |
| **Daily goal** | `daily_activity` is unique on (user, date) and accumulates `xp_earned`. Met when `earned >= daily_goal_xp` (`DEFAULT_DAILY_GOAL_XP = 20`; the learner can pick 10/20/30/50). `daily_goal_just_met(before, after, goal)` is `before < goal <= after`. |
| **Skill states** | `derive_skill_views`: `LOCKED` (previous skill not `COMPLETED`), `AVAILABLE` (0 done), `IN_PROGRESS` (0 < done < total), `COMPLETED` (done == total). The first skill by `order_index` in each course is always unlocked. |
| **Lesson states** | `COMPLETED` if in `user_lesson_progress`. `AVAILABLE` if the skill is unlocked and the previous lesson is done. Otherwise `LOCKED`. |
| **Progress %** | `round(100 * done / total)`. Replays don't double-count, because `user_lesson_progress` is unique per lesson. |
| **Unlock event** | `record_lesson_completion` diffs skill views before/after and reports the first skill that went from `LOCKED` to unlocked as `newly_unlocked_skill`. |
| **Achievements** | `earned_achievement_codes`: `FIRST_LESSON` ≥1 distinct lesson · `PERFECT_LESSON` this completion had 0 mistakes · `XP_100` total XP ≥ 100 · `STREAK_3` streak ≥ 3 · `LESSONS_5` ≥5 *distinct* lessons (counted across all courses). `award_achievements` skips owned ones, and the unique constraint backs it up. |
| **Course switch** | `POST /api/me/course` only changes `active_course_id`. Progress in every course is kept; XP, hearts, gems, streak and goal are shared. |
| **Course reset** | `reset_course_progress`: fails the learner's open attempts in that course, then deletes their `user_lesson_progress` and `user_skill_progress` rows for it. XP, streak, gems, achievements and attempt history stay. |
| **Demo restore** | `seed.restore_demo(db, now)`: deletes every row in every table (reverse FK order) and reseeds. Blocked with `403 DEMO_RESET_DISABLED` when `ALLOW_DEMO_RESET=false`. |
| **Answer checking** | `normalize`: NFC → lowercase → curly apostrophe (U+2019) to `'` → strip `.,!?¿¡` and the Gurmukhi danda `।`/`॥` (U+0964/U+0965) → hyphens to spaces → collapse whitespace → trim. `MULTIPLE_CHOICE`/`FILL_BLANK` use exact normalized equality with no accent tolerance. `WORD_BANK` (tiles joined by spaces, order matters) and `TYPE_ANSWER` go through `match_text` against all `accepted` answers. An accent-only difference is correct with `note: "Watch your accents: <matched option>"`. `strip_accents` removes only U+0300–U+036F (Latin combining marks), so Gurmukhi vowel signs are never stripped. |

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
   - This also made the course reset trivial: deleting progress rows is enough, and the path re-derives.
   - *Alternative:* stored state enums updated on completion, which can drift from the underlying progress (partial writes, content changes, resets).
3. **Lazy heart regeneration.**
   - `gamification.regenerate_hearts` advances `hearts_updated_at` by whole intervals only, which keeps partial progress toward the next heart.
   - *Alternative:* a cron/background job ticking hearts. That means more infrastructure, drift between ticks and work for idle users.
4. **SQLite `BEGIN IMMEDIATE`** (`database.serialize_sqlite_writes`).
   - The game-rules audit found that parallel wrong answers could each read `hearts=5` and write 4 (lost deductions). Taking the write lock at `BEGIN` serializes the read-modify-write.
   - `test_serialize_sqlite_writes_takes_the_write_lock_at_begin` covers the hook.
   - *Alternatives:* an optimistic `version_id_col` with retry. `SELECT … FOR UPDATE` on PostgreSQL in production.
5. **Replay summary is recomputed, not stored.**
   - A `/complete` on a `COMPLETED` attempt (`_neutral_summary`) returns the stored `xp_awarded` and mistakes plus current state, with neutral event fields: `extended=false`, `just_met=false`, `newly_unlocked_skill=null`, `new_achievements=[]`. Heart-practice completions reuse the same builder.
   - *Alternative:* persisting the original summary as JSON. Rejected because the spec forbids JSON columns for user state.
6. **Injected clock and naive UTC.**
   - `now` comes from `deps.get_now`, so tests freeze time with `dependency_overrides[get_now]` (`conftest.FrozenClock`).
   - "Today" is `clock.local_date(now)` in `APP_TIMEZONE`.
   - Datetimes are stored naive UTC because SQLite drops tzinfo. `schemas.UTCDateTime` adds the `Z` on output.
   - `restore_demo` takes `now` from the router rather than reading the clock, so the demo restore is deterministic in tests.
   - *Alternatives:* `datetime.now()` inside rules (untestable), or aware datetimes in SQLite (silently become naive and mix badly).
7. **Match pairs validated client-side.**
   - This gives instant per-tap feedback, and a mismatch costs no heart. The server accepts `{completed: true}` (`answer_check.check_answer`).
   - *Trade-off:* spoofable, but it can't award XP on its own or skip the other exercises.
   - *Alternative:* sending every tap to the server, or submitting the full pairing. That is slower and needs a pairing solution, which the payload already reveals anyway.
8. **Error middleware inside CORS.**
   - `unhandled_error_middleware` is registered before `CORSMiddleware`, so CORS is outermost and 500s carry `Access-Control-Allow-Origin` and the standard error body. Starlette's default 500 handler sits outside CORS, so browsers saw an opaque network error.
   - *Alternative:* a generic `@app.exception_handler(Exception)`, which runs in Starlette's outermost `ServerErrorMiddleware`, outside CORS.
9. **NFC normalization.**
   - `answer_check.normalize` applies `unicodedata.normalize("NFC", …)` first. Decomposed accents (`o` + U+0301) were being flagged as accent mistakes. `test_decomposed_unicode_accents_count_as_exact` covers this.
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
    - SVG flags in `components/ui/CourseFlag.tsx` are used because Windows can't render flag emoji. Punjabi gets a Gurmukhi letter tile instead of a national flag, because the language spans two countries.
    - `turbopack.root` is pinned in `next.config.ts` so a stray lockfile higher up the filesystem isn't picked as the workspace root.
12. **Content package + validator** (`backend/app/content/`).
    - Each course is a plain Python dict built with five tiny builders in `builders.py` (`mc`, `wb`, `mp`, `fb`, `ta`), one file per language, registered in `COURSES`.
    - `validate_course` enforces the exercise contract before anything is inserted: 5–7 exercises and ≥3 types per lesson, all 5 types in Unit 1, ≥3 distinct options with the answer among them, exactly one `___` in a fill-blank sentence, word-bank tiles that can build the first accepted answer with 1–3 distractors and aren't already in order, 3–5 match pairs with no duplicates and no solution, non-empty type-answer alternatives, `#RRGGBB` unit colours.
    - `seed._add_course` calls it, and `test_every_registered_course_passes_validate_course` / `test_validate_course_rejects_broken_content` run it in CI, so broken content fails fast.
    - *Alternatives:* keeping everything in `seed.py` (the original layout, 685 lines for Spanish alone, which didn't scale to four courses), or JSON/YAML files (no builders, no type checking, and the validator would be needed anyway).
13. **Multi-course design.**
    - One `users.active_course_id` pointer. Every course-scoped endpoint resolves it through `progress_service.active_course`, and `/api/course` keeps its one-call contract for "the current course".
    - Skill `order_index` restarts at 1 per course, and `ordered_skills` sorts within one course, so unlocking never crosses courses. Lesson endpoints resolve the lesson's own course (`course_of_lesson`), so they're correct even for a non-active course.
    - XP, hearts, gems, streak, daily goal and achievements stay global to the learner, as in the real product.
    - *Alternatives:* a `user_courses` enrolment table (unnecessary with four fixed courses and no enrolment flow), or per-course XP/streak (more columns and tables for no user-visible benefit).
14. **Heart practice as an attempt mode.**
    - `lesson_attempts.mode` (`LESSON`/`PRACTICE`) reuses the whole attempt machinery: solutions stay hidden, answers are stored and idempotent, and completion needs every answer. `submit_answer` and `complete_attempt` branch on the mode in exactly two places.
    - The server picks the lesson (weakest by `best_mistakes`, then oldest), so the client can't aim practice at a lesson it hasn't unlocked.
    - *Alternatives:* a separate practice endpoint family (duplicated guards), or letting the client choose the lesson (would need its own lock checks).
15. **Reset design and the XP-farming guard.**
    - A course reset deletes `user_lesson_progress`/`user_skill_progress` for that course and fails its open attempts, but keeps XP, streak, gems, achievements and every `lesson_attempts` row.
    - Without a guard, reset → replay would pay first-completion XP again. `lesson_service.completed_before` checks for an earlier `COMPLETED` `LESSON` attempt; `complete_attempt` uses it to pay `PRACTICE_XP`, and `lesson_meta` uses it so the intro screen shows the same amount (`is_practice`, `xp_reward`).
    - The seed writes the demo learner's 6 completed attempts (3 first completions at 10 XP + 3 replays at 5 XP = the seeded 45 XP, each with 1 mistake), so the seeded lessons are covered too (`test_seeded_attempt_history_backs_the_xp`).
    - `complete_attempt` re-checks the lesson lock, so an attempt started before a reset can't complete a lesson the reset re-locked (`test_in_flight_attempt_cannot_complete_a_lesson_locked_by_a_reset`).
    - The demo restore wipes everything and can be turned off with `ALLOW_DEMO_RESET=false`.
    - *Alternatives:* soft-deleting progress with a `reset_at` column (more query complexity everywhere), or refusing resets (the user asked for them).
16. **Latin-only accent forgiveness.**
    - The first version stripped every nonspacing mark (Unicode category `Mn`). Gurmukhi vowel signs and the nasal sign are combining marks too, so a misspelled Punjabi word would have been "correct, watch your accents". `strip_accents` now removes only U+0300–U+036F.
    - `test_strip_accents_preserves_gurmukhi_vowel_signs` and `test_gurmukhi_missing_vowel_sign_is_wrong_not_an_accent_note` pin it.
    - *Alternatives:* a per-language flag on the course (more config for the same effect), or no accent tolerance (harsh for Spanish/French beginners).
17. **Branding override.** The spec asked for an original name. The user explicitly asked for "Duolingo", so the name lives in one constant per side (`APP_NAME` in `frontend/lib/brand.ts`, and `APP_NAME` in `backend/app/config.py`, env-overridable). The mascot Pico and every icon stay original SVG. *Alternative:* keep the earlier original product name against the user's explicit instruction.
18. **Dark-mode token strategy.**
    - Components use semantic tokens (`bg-card`, `bg-surface`, `text-ink`, `text-muted`, `*-light` backgrounds with `text-*-ink`). `app/globals.css` defines them in `@theme` and overrides only the values under `:root[data-theme="dark"]`, so no component needs `dark:` variants.
    - `THEME_INIT_SCRIPT` runs inline in `<head>` and sets `data-theme` before paint (no flash). `<html>` has `suppressHydrationWarning` because the script changes the attribute before React hydrates.
    - The preference is per device (`localStorage`), because it depends on the screen more than on the learner.
    - *Alternatives:* Tailwind `dark:` variants on every element (doubles the class lists and is easy to miss), or storing the theme on the server (a flash on first paint until `/api/me` loads).
19. **Settings as typed columns with a validated partial PATCH.** Six fields, each with its own column and validator in `SettingsIn`. The endpoint returns the full `MeOut`, so the client replaces its cache in one round trip. *Alternative:* a JSON `preferences` column, which the spec forbids for user state and which can't be constrained.
20. **Project subagents** (`.claude/agents/`: `spanish-content-reviewer`, `game-rules-auditor`, `verifier`, `docs-writer`) were used for review and verification, while the main session did all building. Their findings were fixed in the `phase-3` commit:
    - ambiguous fill-blank options (one grammatical blank per sentence)
    - extra accepted answers
    - the heart race
    - CORS on 500s
    - NFC normalization

---

## 9. Security and integrity

- **Why the server owns XP, hearts and streak.** Anything computed on the client can be edited in DevTools. The client never sends XP, hearts, streak, progress or unlocks. It sends answers, and the server decides correctness, deductions and rewards inside a transaction.
- **Settings can't touch game state.** `SettingsIn` declares only `display_name`, `avatar_color`, `daily_goal_xp`, `sound_effects`, `daily_reminder` and `achievement_alerts`. Pydantic drops any other key, so `PATCH /api/me/settings {"xp": 9999, "hearts": 99, "gems": 1}` changes nothing (covered by `test_settings.py::test_patch_ignores_protected_fields`). `daily_goal_xp` is limited to 10/20/30/50.
- **Solutions never leave the server.**
  - `schemas.ExerciseOut` has no `solution` field, and `_create_attempt` builds it explicitly from `id/type/prompt/payload`.
  - `test_start_creates_attempt_and_hides_solutions` and `test_type_answer_solutions_never_leak_in_start` guard this, and the smoke test asserts it against the live server.
  - `correct_answer` is revealed only *after* an answer is stored for that exercise.
- **Match-pairs trade-off.** The pairs are in the `payload` (the client needs them to render), so validating on the client reveals nothing new. A forged `{completed: true}` only skips one exercise's feedback. It can't award XP, because completion still requires every other exercise to be answered through the server.
- **Reset integrity.** A course reset can't farm XP (`completed_before`), can't be raced by an in-flight attempt (open attempts are failed, and `complete_attempt` re-checks the lock), and the destructive demo restore can be disabled (`ALLOW_DEMO_RESET`).
- **Still spoofable without auth.**
  - Anyone who can reach the API can act as the seeded learner. `deps.get_current_user` is the single seam where real auth would go.
  - Answers can be learned by answering wrong, because `correct_answer` is returned. In a lesson that costs hearts. In heart practice it costs nothing, but practice only serves lessons the learner has already completed (or a course's first lesson).
  - Match pairs can be auto-completed.
  - With `ALLOW_DEMO_RESET=true` (the default), anyone who can reach the API can wipe and reseed the database.
  - There is no rate limiting.
- **CORS** is restricted to `CORS_ORIGINS`, with methods `GET`/`POST`/`PATCH` and header `Content-Type` only. `test_cors_rejects_unknown_origins` and `test_cors_allows_patch` cover it.
- **Errors never leak stack traces.** Every error goes through `_error()` in `main.py` as `{"detail": {"code", "message"}}`, and unexpected exceptions are logged server-side only.
- **Ownership checks.** `_get_attempt` returns 404 for another user's attempt, and exercises must belong to the attempt's lesson.

### Known limitation: changing the daily goal mid-day

`daily_goal.just_met` is computed at completion time as `before < goal <= after` using the learner's *current* `daily_goal_xp`. If the learner raises the goal after meeting it, the next lesson that crosses the new goal fires `just_met` a second time. If they lower it below today's XP, it never fires today. Only the celebration flag is affected; XP, the streak and stored state are not. A fix would apply a changed goal from the next local day (store the pending goal with an effective date).

---

## 10. Testing

- **pytest.** `backend/tests/` has **267 tests**, all passing. They use in-memory SQLite (`sqlite://` + `StaticPool` + `check_same_thread=False`) and a frozen clock (`FIXED_NOW = 2026-01-15 06:30 UTC`, which is noon in Kolkata).
  - `conftest.py` pins every env var *before* importing `app`, so a demo `backend/.env` can't change the rules under test.
  - It overrides `get_db` and `get_now` and never enters the TestClient context manager, so the lifespan auto-seed never runs.

  | File | Tests | Covers |
  |---|---|---|
  | `test_answer_check.py` | 62 | normalize, accent notes, multiple accepted answers, word-bank order, decomposed Unicode, invalid payloads, Latin-only `strip_accents`, Gurmukhi exact/misspelled/word-bank answers, curly apostrophes, danda stripping, hyphens to spaces |
  | `test_gamification.py` | 37 | regen (partial progress, cap, clock reset), `lose_heart` floor, refill with, without and with exact gems, streak cases, `display_streak`, XP, `just_met`, achievement codes/awarding |
  | `test_lesson_flow.py` | 37 | the API end to end: hidden solutions, locked/0-heart guards, regen before the zero check, duplicate answers, running out of hearts, base/perfect/practice XP, completion idempotency, unanswered completion, daily goal crossing once, timezone-day streaks, broken-streak display, each achievement once |
  | `test_settings.py` | 28 | `PATCH /api/me/settings`: partial updates, persistence, explicit nulls, name stripping and length limits, allowed goals, whole-patch rejection, the new goal driving goal tracking, protected fields (`xp`/`hearts`/`gems`/…) ignored, CORS for `PATCH` |
  | `test_seed.py` | 26 | every registered course is seeded and matches its module, `validate_course` passes/rejects, §7 invariants, Unit 1 of every course uses every type, the demo learner's stats/activity/progress/achievements, the seeded attempt history backing the 45 XP, rivals, dates relative to `now`, CLI idempotency |
  | `test_api_misc.py` | 21 | `/api/me` regen-on-read, refill, profile, leaderboard, achievements, the error format (404/405/422/500), CORS, the `BEGIN IMMEDIATE` hook, the clock override |
  | `test_practice.py` | 15 | practice start shape and mode, works at 0 hearts, weakest-lesson choice, active course, free mistakes, +1 heart and nothing else, capped at max, idempotent completion, needs every answer |
  | `test_courses.py` | 14 | `/api/courses`, switching (valid, unknown, invalid), the tree follows the active course, progress kept per course, lessons in non-active courses, per-course unlocks, profile courses |
  | `test_progress.py` | 14 | state derivation, sequential unlocking, progress rounding, no double-counting on replay, the course tree |
  | `test_reset.py` | 13 | reset validation, active-course-only reset, practice XP after reset (seeded and played lessons), full XP for never-completed lessons, in-flight attempts, other users untouched, demo restore (fresh, repeatable, disabled → `403 DEMO_RESET_DISABLED`) |

- **Smoke test.** `backend/scripts/smoke_test.py` makes 22 checks against the live server on a fresh seed:
  - health, the seeded state and `403 LESSON_LOCKED`
  - no solutions in `/start`
  - wrong answer → 4 hearts, and a duplicate submission doesn't charge again
  - `409 INCOMPLETE_ATTEMPT`
  - +10 XP → 55 total, streak 3→4, and Introductions COMPLETED with Common Words unlocked
  - an idempotent second `/complete`
  - persisted `/api/me` and `/api/course`
- **Frontend.** `npx tsc --noEmit`, `npm run lint` and `npm run build` are clean. Playwright runs against the production build (in the main session), all with zero console errors:
  - the original journey, 37/37 (heart loss, a full lesson, streak 3→4 and the unlock, hard-refresh persistence, the out-of-hearts modal and refill)
  - a perfect lesson, 9/9 (+15 XP, Flawless toast)
  - new features, 32/32 (dark-mode and settings persistence, a perfect French lesson for +15 XP, a Punjabi lesson, the course switcher, heart practice 4→5 hearts, course reset, demo restore, no overflow at 375px in dark mode)

---

## 11. Production path

- **PostgreSQL + Alembic.** Replace `create_all` with migrations. `database.py` currently passes SQLite-only `connect_args` and installs the `BEGIN IMMEDIATE` hook only for the SQLite dialect. On Postgres, use `SELECT … FOR UPDATE` on the user row (or optimistic versioning) for the read-modify-write in answer/complete. Add `course_id` to `skills` (or a composite key) so per-course `order_index` uniqueness is enforced by the DB.
- **Auth (JWT/OAuth).** Replace `deps.get_current_user` with token verification. Every user-scoped query already gets the user from that dependency, so nothing else changes. Remove or admin-gate the demo restore, and add rate limiting on `/answer`.
- **Leaderboard.** Use a Redis sorted set (`ZINCRBY` on XP award, `ZREVRANGE`/`ZREVRANK` to read) with weekly keys for leagues, instead of `ORDER BY xp` over all users.
- **Background jobs.** Hearts and streaks stay lazy. Jobs would handle real streak-reminder pushes (replacing the in-app banner + same-tab browser notification), weekly league rollover and analytics, via a queue (e.g. Celery/RQ/Cloud Tasks).
- **Media.** Use object storage + a CDN for audio and images (listening/speaking exercises), with URLs in exercise `payload`.
- **Containerized deploy.** Build separate images for the API (uvicorn/gunicorn workers) and the Next.js app. Use managed Postgres and Redis, with config via the same env vars `Settings` already reads.
- **Content.** Keep the `content/` format and `validate_course`, but feed them from an authoring tool or CMS, and version content changes so progress rows survive edits.

---

## 12. Likely interview questions

1. **How do you stop a user from giving themselves XP?** The client never sends XP. `lesson_service.complete_attempt` computes it from the attempt's server-recorded `mistakes` and whether the lesson was completed before (`user_lesson_progress` plus `completed_before`), via `gamification.lesson_xp`.

2. **What if the user double-clicks Complete?** The conditional `UPDATE … WHERE status='IN_PROGRESS'` lets exactly one request claim the attempt. The other sees `rowcount != 1` and gets `_neutral_summary` with `already_completed: true` and nothing awarded.

3. **What if they resubmit an answer to avoid losing a heart, or retry after a timeout?** `attempt_answers` is unique on (`attempt_id`, `exercise_id`). `submit_answer` returns the stored result without charging again. A concurrent duplicate hits `IntegrityError`, rolls back and returns the winner's result.

4. **How do hearts regenerate without a cron job?** Lazily. `regenerate_hearts` computes `min(MAX, stored + floor(elapsed/interval))` whenever hearts are read or changed. It advances `hearts_updated_at` by whole intervals only, so partial progress isn't lost.

5. **Why does `/api/me` not write regenerated hearts back?** It doesn't need to. `effective_hearts` is a pure computation from stored hearts and the stored clock. Writes happen only when state changes (deduction, refill, start), which keeps GETs side-effect free.

6. **How is the streak computed, and how does it break?** On lesson completion, `next_streak` keeps it (same day), increments it (yesterday) or resets it to 1. Nothing runs at midnight. `display_streak` shows 0 when the last activity is before yesterday, and the next completion resets it to 1. Heart practice doesn't count.

7. **What does "today" mean?** `clock.local_date(now)`: the calendar date in `APP_TIMEZONE`. A test (`test_streak_follows_the_app_timezone_day`) checks that the day boundary follows Kolkata, not UTC.

8. **How do you test time-dependent rules?** Rules take `now`/`today` as parameters. The API gets `now` from `deps.get_now`, which the tests override with `FrozenClock` and advance explicitly.

9. **Why is skill state derived instead of stored?** `derive_skill_views` is a pure function of completed lesson IDs, so state can't drift from progress. Stored enums would need to be updated correctly on every write path forever, including resets.

10. **How does unlocking work across units?** Within a course, `skills.order_index` runs across units. `ordered_skills` flattens the course's units and sorts by it, and each skill is unlocked iff the previous one is `COMPLETED`.

11. **How do you know which skill was just unlocked?** `record_lesson_completion` derives views before and after adding the lesson and returns the first skill that changed from `LOCKED`.

12. **How does `just_met` fire only once?** `daily_goal_just_met(before, after, goal)` is `before < goal <= after`, computed from today's `daily_activity.xp_earned` before and after adding this lesson's XP. The next lesson starts above the goal, so it's false. The exception is a goal changed mid-day (see the known limitation in section 9).

13. **How do achievements unlock only once?** `award_achievements` filters out codes the user already owns, and `unique(user_id, achievement_id)` is the DB-level backstop. It all runs in the completion transaction, so a failure rolls back XP and achievements together.

14. **Why is match pairs validated on the client?** Instant per-tap feedback, and the pairs are already in the payload (there's nothing secret to protect). A mismatch costs no heart. The server accepts `{completed: true}`. Forging it skips one exercise but can't award XP by itself.

15. **How do you guarantee solutions never leak?** They live in a separate `solution` column that is never mapped onto a response schema. `ExerciseOut` has only `id/type/prompt/payload`, and tests plus the smoke test assert it.

16. **How does accent-tolerant checking work?** `match_text` first compares `normalize()`d strings against every accepted answer. If none match, it compares with accents stripped (`strip_accents`: NFD, remove U+0300–U+036F, NFC). An accent-only match is correct with `note: "Watch your accents: …"`. Multiple choice and fill-blank are exact.

17. **What race condition did you find, and how did you fix it?** Parallel wrong answers each read `hearts=5` and each wrote 4. The fix is `database.serialize_sqlite_writes`, which disables pysqlite's implicit BEGIN and issues `BEGIN IMMEDIATE`, so the write lock is taken before the first read. On Postgres you would use `SELECT … FOR UPDATE`.

18. **Why SQLite?** Zero setup, a single file, and it's enough for a single-user demo. Its limits (write concurrency, tz-naive datetimes, FKs off by default) are handled explicitly. Postgres + Alembic is the production path.

19. **How is the error format kept consistent?** `AppError(status, code, message)` is raised by services, and `main.py` has handlers for `AppError`, validation errors and HTTP exceptions, plus a middleware for unexpected exceptions. They all go through `_error()`. On the client, `lib/api.ts` parses `detail.code` into `ApiError`, and `isApiError(err, "OUT_OF_HEARTS")` drives UI branches.

20. **Why does the 500 handler sit in a middleware?** A plain `Exception` handler runs in Starlette's outermost `ServerErrorMiddleware`, outside CORS, so the browser saw a CORS failure instead of the JSON error. The middleware is registered before `CORSMiddleware`, which places it inside.

21. **How does the lesson player avoid inconsistent UI states?** It's a reducer with explicit phases. Actions are ignored in the wrong phase (e.g. `ANSWER_CHANGED` outside `ANSWERING`), it never auto-advances, and buttons disable during `CHECKING`/`SUBMITTING`.

22. **How would you add a sixth exercise type?** Add the enum value in `models.ExerciseType`, a branch in `answer_check.check_answer`, a builder and a validation branch in `content/builders.py`, the payload type in `lib/types.ts`, one component, and one `REGISTRY` entry. The mapped registry type makes the compiler flag a missing entry.

23. **How does the frontend know hearts changed?** Answer responses include `hearts`, and the player shows that value. It also calls `UserStatsContext.refresh()`. The context schedules a re-read at `next_heart_at`, so regenerated hearts appear without a reload.

24. **Why no Redux?** The only shared server state is one `/api/me` object. Context plus `refresh()`/`replace()` covers it, and per-page data uses `useApi`. The spec also forbids Redux/Zustand.

25. **How would you add a fifth language?** Write `backend/app/content/<lang>.py` exporting `COURSE` with the builders, add it to `COURSES` in `content/__init__.py`, and reseed. `validate_course` rejects malformed content at seed time, and the seed tests iterate `COURSES`, so they cover it automatically. On the frontend, add a flag to `CourseFlag` and, optionally, accented-letter buttons to `SPECIAL_CHARACTERS` in `TypeAnswer.tsx`; unknown codes fall back to the emoji.

26. **Why doesn't accent forgiveness break Punjabi?** Gurmukhi vowel signs are Unicode combining marks, like Latin accents. Stripping all combining marks would turn a misspelling into "correct, watch your accents". `strip_accents` removes only the Latin combining block U+0300–U+036F. `normalize` also strips the danda (`।`, U+0964, and `॥`, U+0965), so learners can type it or not. Romanized answers are just extra entries in `accepted`, generated by `_roman` in `punjabi.py`.

27. **Can a course reset be used to farm XP?** No. Progress rows are deleted, but `lesson_attempts` are kept. `completed_before` finds an earlier completed `LESSON` attempt and `complete_attempt` pays `PRACTICE_XP` instead of first-completion XP. The seed writes attempt rows for the demo learner's history so seeded lessons are covered too. The intro screen uses the same helper, so the XP it promises matches the payout.

28. **What happens to a lesson that's open in another tab when the course is reset?** `reset_course_progress` marks the learner's `IN_PROGRESS` attempts in that course `FAILED`, so `/complete` returns `409 ATTEMPT_FAILED`. Independently, `complete_attempt` re-checks `lesson_status` and returns `409 LESSON_LOCKED` if the lesson is now locked.

29. **How does heart practice avoid becoming an XP or streak exploit?** It's a separate attempt `mode`. `complete_attempt` branches before any progress, XP, streak, daily-goal or achievement code runs, sets `xp_awarded = 0` and only adds one heart if below max. Mistakes are free because `submit_answer` calls `lose_heart` only in `LESSON` mode. The server chooses the lesson, so practice can't reach a locked lesson.

30. **Why are settings a PATCH that returns the whole `/api/me`?** The client already caches `/api/me` in `UserStatsContext`. Returning the full `MeOut` lets `useSettingsSave` call `replace()` in one round trip, so the daily goal card, avatar and toggles all update together. PATCH semantics (only sent fields change) let each toggle save independently.

31. **How does dark mode avoid a flash of the wrong theme?** `THEME_INIT_SCRIPT` is inlined in `<head>` by `app/layout.tsx` and sets `document.documentElement.dataset.theme` from `localStorage` (or `prefers-color-scheme`) before first paint. The colours are CSS variables in `globals.css` overridden under `:root[data-theme="dark"]`, so no component re-renders to switch theme.

32. **How are sound effects shipped without audio files?** `lib/sound.ts` synthesizes short tones with the Web Audio API (`OscillatorNode` + `GainNode` envelopes) for `correct`, `wrong`, `complete` and `heart`. `playSound` is a no-op when the learner's `sound_effects` setting is off and swallows errors, because audio is decorative.

33. **How does the streak reminder work without a backend job?** The home page shows a banner when `me.settings.daily_reminder` is on and `me.streak_extended_today` is false. If notification permission was granted (requested when the toggle is switched on), `maybeSendStreakReminder` also shows one browser notification per day, deduplicated with a `localStorage` date. A real push reminder would need a scheduled job and Web Push.

34. **What's still insecure?** There is no auth: anyone can act as the seeded learner and, unless `ALLOW_DEMO_RESET=false`, restore the demo. Answers can be learned by answering wrong (costs hearts in a lesson, free in practice on already-completed lessons), match pairs can be auto-completed, and there is no rate limiting. Auth slots into `deps.get_current_user`.

35. **How would you scale the leaderboard?** Use a Redis sorted set updated in the completion transaction's after-commit hook, with weekly keys for leagues and `ZREVRANK` for "your rank". Today it's `ORDER BY xp DESC, id` over `users`, which is fine for six rows.

36. **How is the demo kept repeatable?** `python -m app.seed --reset` drops and recreates all tables, then seeds dates relative to "today" in `APP_TIMEZONE`, so the streak is always 3 ending yesterday. Settings → Restore demo data does the same through `POST /api/me/reset {"scope": "demo"}`. `test_seed_cli_is_idempotent`, `test_seed_cli_reset_rebuilds_the_same_data` and `test_demo_reset_is_repeatable` guard it. `AUTO_SEED` also seeds an empty DB on startup.

37. **How does the seeded history stay consistent with the achievements?**
    - Arnav's three completed lessons each have `best_mistakes=1`, so `PERFECT_LESSON` stays locked.
    - 45 XP = three first completions (10 each) + three practice replays (5 each), spread as 15 XP/day over the previous 3 days, and backed by six `COMPLETED` attempt rows with 1 mistake each.
    - `FIRST_LESSON` and `STREAK_3` are unlocked.
