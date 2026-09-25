"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useEffectEvent, useReducer, useState } from "react";

import { useUserStats } from "@/context/UserStatsContext";
import { api, errorMessage, isApiError } from "@/lib/api";
import { playSound } from "@/lib/sound";
import type { AnswerPayload, AnswerResult, AttemptStart, CompletionSummary, LessonMeta } from "@/lib/types";

import { Mascot } from "../Mascot";
import { Button, buttonClasses } from "../ui/Button";
import { BoltIcon, CloseIcon, HeartIcon } from "../ui/icons";
import { Modal } from "../ui/Modal";
import { ErrorState, Skeleton } from "../ui/States";
import { ExerciseRenderer } from "./ExerciseRenderer";
import { FeedbackBar } from "./FeedbackBar";
import { LessonComplete } from "./LessonComplete";
import { OutOfHeartsModal } from "./OutOfHeartsModal";

/*
 * INTRO → ANSWERING → CHECKING → FEEDBACK → (next) ANSWERING … → SUBMITTING → COMPLETE
 *                                    └→ OUT_OF_HEARTS
 * Plus LOADING / LOAD_ERROR before the intro and STARTING while the attempt is created.
 */
type Phase =
  | "LOADING"
  | "LOAD_ERROR"
  | "INTRO"
  | "STARTING"
  | "ANSWERING"
  | "CHECKING"
  | "FEEDBACK"
  | "SUBMITTING"
  | "COMPLETE"
  | "OUT_OF_HEARTS";

interface State {
  phase: Phase;
  meta: LessonMeta | null;
  attempt: AttemptStart | null;
  index: number;
  answer: AnswerPayload | null;
  result: AnswerResult | null;
  hearts: number | null;
  summary: CompletionSummary | null;
  error: unknown;
  notice: string | null;
}

type Action =
  | { type: "META_LOADED"; meta: LessonMeta }
  | { type: "LOAD_FAILED"; error: unknown }
  | { type: "START" }
  | { type: "STARTED"; attempt: AttemptStart }
  | { type: "START_FAILED"; error: unknown }
  | { type: "OUT_OF_HEARTS" }
  | { type: "ANSWER_CHANGED"; answer: AnswerPayload | null }
  | { type: "CHECK" }
  | { type: "CHECKED"; result: AnswerResult }
  | { type: "CHECK_FAILED"; error: unknown }
  | { type: "NEXT" }
  | { type: "SUBMIT" }
  | { type: "COMPLETED"; summary: CompletionSummary }
  | { type: "SUBMIT_FAILED"; error: unknown }
  | { type: "REFILLED" };

const initialState: State = {
  phase: "LOADING",
  meta: null,
  attempt: null,
  index: 0,
  answer: null,
  result: null,
  hearts: null,
  summary: null,
  error: null,
  notice: null,
};

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "META_LOADED":
      return { ...state, phase: "INTRO", meta: action.meta };
    case "LOAD_FAILED":
      return { ...state, phase: "LOAD_ERROR", error: action.error };
    case "START":
      return { ...state, phase: "STARTING", error: null, notice: null };
    case "STARTED":
      return {
        ...state,
        phase: "ANSWERING",
        attempt: action.attempt,
        meta: action.attempt.lesson,
        hearts: action.attempt.hearts,
        index: 0,
        answer: null,
        result: null,
        summary: null,
      };
    case "START_FAILED":
      return { ...state, phase: "INTRO", error: action.error };
    case "OUT_OF_HEARTS":
      return { ...state, phase: "OUT_OF_HEARTS", hearts: 0 };
    case "ANSWER_CHANGED":
      return state.phase === "ANSWERING" ? { ...state, answer: action.answer, error: null } : state;
    case "CHECK":
      return { ...state, phase: "CHECKING", error: null };
    case "CHECKED":
      return { ...state, phase: "FEEDBACK", result: action.result, hearts: action.result.hearts };
    case "CHECK_FAILED":
      return { ...state, phase: "ANSWERING", error: action.error };
    case "NEXT":
      return { ...state, phase: "ANSWERING", index: state.index + 1, answer: null, result: null };
    case "SUBMIT":
      return { ...state, phase: "SUBMITTING", error: null };
    case "COMPLETED":
      return { ...state, phase: "COMPLETE", summary: action.summary };
    case "SUBMIT_FAILED":
      return { ...state, error: action.error };
    case "REFILLED":
      return { ...initialState, phase: "INTRO", meta: state.meta, notice: "Hearts refilled! Ready to try again?" };
  }
}

interface LessonPlayerProps {
  /** The lesson to play. Omit with `practice` for heart practice (server picks the lesson). */
  lessonId?: number;
  /** Heart practice: mistakes are free and finishing restores a heart. */
  practice?: boolean;
}

export function LessonPlayer({ lessonId, practice = false }: LessonPlayerProps) {
  const router = useRouter();
  const { me, refresh } = useUserStats();
  // Practice has no lesson to preview: it opens straight on its own intro.
  const [state, dispatch] = useReducer(reducer, practice ? { ...initialState, phase: "INTRO" } : initialState);
  const soundOn = me?.settings.sound_effects ?? false;
  const [confirmQuit, setConfirmQuit] = useState(false);
  const [loadVersion, setLoadVersion] = useState(0);

  const { phase, meta, attempt, index, answer, result, hearts, summary } = state;
  const exercises = attempt?.exercises ?? [];
  const exercise = exercises[index] ?? null;
  const isLast = index === exercises.length - 1;
  const inProgress = phase === "ANSWERING" || phase === "CHECKING" || phase === "FEEDBACK";

  useEffect(() => {
    if (lessonId === undefined) return;
    let cancelled = false;
    api.lesson(lessonId).then(
      (loaded) => !cancelled && dispatch({ type: "META_LOADED", meta: loaded }),
      (error: unknown) => !cancelled && dispatch({ type: "LOAD_FAILED", error }),
    );
    return () => {
      cancelled = true;
    };
  }, [lessonId, loadVersion]);

  async function start() {
    dispatch({ type: "START" });
    try {
      const attempt = practice || lessonId === undefined ? await api.startPractice() : await api.startLesson(lessonId);
      dispatch({ type: "STARTED", attempt });
    } catch (error) {
      if (isApiError(error, "OUT_OF_HEARTS")) {
        await refresh();
        dispatch({ type: "OUT_OF_HEARTS" });
      } else {
        dispatch({ type: "START_FAILED", error });
      }
    }
  }

  async function check(override?: AnswerPayload) {
    const submitted = override ?? answer;
    if (!attempt || !exercise || !submitted || phase !== "ANSWERING") return;
    dispatch({ type: "CHECK" });
    try {
      const checked = await api.answer(attempt.attempt_id, exercise.id, submitted);
      dispatch({ type: "CHECKED", result: checked });
      playSound(checked.correct ? "correct" : "wrong", soundOn);
      void refresh(); // hearts shown elsewhere come from the server
    } catch (error) {
      dispatch({ type: "CHECK_FAILED", error });
    }
  }

  async function submit() {
    if (!attempt) return;
    dispatch({ type: "SUBMIT" });
    try {
      const completed = await api.complete(attempt.attempt_id);
      dispatch({ type: "COMPLETED", summary: completed });
      playSound(completed.mode === "PRACTICE" && completed.hearts_restored > 0 ? "heart" : "complete", soundOn);
      void refresh();
    } catch (error) {
      dispatch({ type: "SUBMIT_FAILED", error });
    }
  }

  function next() {
    if (phase !== "FEEDBACK" || !result) return;
    if (result.out_of_hearts) dispatch({ type: "OUT_OF_HEARTS" });
    else if (isLast) void submit();
    else dispatch({ type: "NEXT" });
  }

  function quit() {
    if (inProgress) setConfirmQuit(true);
    else router.push("/");
  }

  const onKeyDown = useEffectEvent((event: KeyboardEvent) => {
    if (event.key !== "Enter" || event.repeat || confirmQuit) return;
    // Controls outside the exercise (footer, modals) handle Enter natively.
    // Inside it, Enter means Check even when an option button has focus.
    const target = event.target as HTMLElement | null;
    if (target?.closest("button, a") && !target.closest("[data-exercise-area]")) return;
    if (phase === "ANSWERING" && answer) {
      event.preventDefault();
      void check();
    } else if (phase === "FEEDBACK") {
      event.preventDefault();
      next();
    } else if (phase === "INTRO") {
      event.preventDefault();
      void start();
    }
  });

  useEffect(() => {
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  // ── Screens ────────────────────────────────────────────────────────────────

  if (phase === "LOADING") {
    return (
      <div className="mx-auto flex min-h-screen max-w-lg flex-col items-center justify-center gap-4 px-4" role="status" aria-label="Loading lesson">
        <Skeleton className="h-28 w-28 rounded-full" />
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-5 w-48" />
      </div>
    );
  }

  if (phase === "LOAD_ERROR" || (!meta && !practice)) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center px-4">
        <ErrorState error={state.error} onRetry={() => setLoadVersion((v) => v + 1)} title="Couldn't load this lesson" />
        <Link href="/" className={buttonClasses("ghost")}>
          Back to path
        </Link>
      </div>
    );
  }

  if (phase === "COMPLETE" && summary) {
    return (
      <LessonComplete
        summary={summary}
        showAchievements={me?.settings.achievement_alerts ?? true}
        onContinue={() => {
          void refresh();
          router.push("/");
        }}
      />
    );
  }

  if (practice && (phase === "INTRO" || phase === "STARTING")) {
    return (
      <div className="flex min-h-screen flex-col">
        <header className="mx-auto flex w-full max-w-3xl items-center px-4 pt-5">
          <Link href="/" aria-label="Back to path" className="grid h-11 w-11 place-items-center rounded-xl text-muted hover:bg-surface">
            <CloseIcon className="h-7 w-7" />
          </Link>
        </header>
        <main className="mx-auto flex w-full max-w-lg flex-1 flex-col items-center justify-center gap-5 px-4 py-8 text-center">
          <Mascot mood="cheer" className="h-28 w-28" />
          <div>
            <p className="text-sm font-extrabold tracking-wide text-muted uppercase">
              {me ? `${me.active_course.title} · ` : ""}Heart practice
            </p>
            <h1 className="mt-1 text-3xl font-black">Practice to earn a heart</h1>
            <p className="mt-2 text-muted">
              Review a lesson you&apos;ve already met. Mistakes don&apos;t cost hearts here, and finishing gives you
              one heart back.
            </p>
          </div>
          {me && (
            <span className="flex items-center gap-1 rounded-xl bg-danger-light px-3 py-2 font-extrabold text-heart">
              <HeartIcon className="h-5 w-5" /> {me.hearts} / {me.max_hearts} hearts
            </span>
          )}
          {state.error !== null && (
            <p role="alert" className="font-bold text-danger">
              {errorMessage(state.error)}
            </p>
          )}
        </main>
        <footer className="border-t-2 border-line">
          <div className="mx-auto flex max-w-3xl flex-col gap-3 px-4 py-5 sm:flex-row sm:justify-end sm:py-7">
            <Button onClick={() => void start()} disabled={phase === "STARTING"} className="sm:min-w-44">
              {phase === "STARTING" ? "Starting…" : "Start practice"}
            </Button>
          </div>
        </footer>
      </div>
    );
  }

  if (!meta) return null;

  if (phase === "INTRO" || phase === "STARTING" || (phase === "OUT_OF_HEARTS" && !attempt)) {
    const locked = meta.status === "LOCKED";
    return (
      <div className="flex min-h-screen flex-col">
        <header className="mx-auto flex w-full max-w-3xl items-center px-4 pt-5">
          <Link href="/" aria-label="Back to path" className="grid h-11 w-11 place-items-center rounded-xl text-muted hover:bg-surface">
            <CloseIcon className="h-7 w-7" />
          </Link>
        </header>
        <main className="mx-auto flex w-full max-w-lg flex-1 flex-col items-center justify-center gap-5 px-4 py-8 text-center">
          <div
            className="grid h-28 w-28 place-items-center rounded-full border-b-8 text-5xl"
            style={{ backgroundColor: meta.unit_color, borderColor: "rgba(0,0,0,.2)" }}
            aria-hidden="true"
          >
            {meta.skill_icon}
          </div>
          <div>
            <p className="text-sm font-extrabold tracking-wide text-muted uppercase">
              {meta.unit_title} · {meta.skill_title}
            </p>
            <h1 className="mt-1 text-3xl font-black">{meta.title}</h1>
            <p className="mt-1 font-bold text-muted">
              Lesson {meta.order_index} of {meta.lessons_in_skill} · {meta.exercise_count} exercises
            </p>
          </div>
          <div className="flex flex-wrap justify-center gap-3 font-extrabold">
            <span className="flex items-center gap-1 rounded-xl bg-gold-light px-3 py-2 text-gold-ink">
              <BoltIcon className="h-5 w-5" /> +{meta.xp_reward} XP{meta.is_practice ? " (practice)" : ""}
            </span>
            {me && (
              <span className="flex items-center gap-1 rounded-xl bg-danger-light px-3 py-2 text-heart">
                <HeartIcon className="h-5 w-5" /> {me.hearts} hearts
              </span>
            )}
          </div>
          {meta.is_practice && <p className="text-sm text-muted">You&apos;ve completed this lesson. Replaying it earns practice XP.</p>}
          {!meta.is_practice && !locked && <p className="text-sm text-muted">Finish with no mistakes for a perfect bonus.</p>}
          {state.notice && <p className="font-bold text-primary-ink">{state.notice}</p>}
          {state.error !== null && (
            <p role="alert" className="font-bold text-danger">
              {errorMessage(state.error)}
            </p>
          )}
        </main>
        <footer className="border-t-2 border-line">
          <div className="mx-auto flex max-w-3xl flex-col gap-3 px-4 py-5 sm:flex-row sm:justify-end sm:py-7">
            {locked ? (
              <p className="self-center font-bold text-muted">Complete the previous lessons to unlock this one.</p>
            ) : (
              <Button onClick={() => void start()} disabled={phase === "STARTING"} className="sm:min-w-44">
                {phase === "STARTING" ? "Starting…" : meta.is_practice ? "Practice" : "Start lesson"}
              </Button>
            )}
          </div>
        </footer>
        {phase === "OUT_OF_HEARTS" && <OutOfHeartsModal onRefilled={() => dispatch({ type: "REFILLED" })} />}
      </div>
    );
  }

  // ANSWERING / CHECKING / FEEDBACK / SUBMITTING / OUT_OF_HEARTS (mid-lesson)
  const answeredCount = index + (phase === "FEEDBACK" || phase === "SUBMITTING" || phase === "OUT_OF_HEARTS" ? 1 : 0);
  const progressPct = exercises.length ? (answeredCount / exercises.length) * 100 : 0;
  const status = result ? (result.correct ? "correct" : "incorrect") : "idle";

  return (
    <div className="flex min-h-screen flex-col">
      <header className="mx-auto flex w-full max-w-3xl items-center gap-4 px-4 pt-5">
        <button
          type="button"
          onClick={quit}
          aria-label="Quit lesson"
          className="grid h-11 w-11 shrink-0 place-items-center rounded-xl text-muted hover:bg-surface"
        >
          <CloseIcon className="h-7 w-7" />
        </button>
        <div
          className="h-4 flex-1 overflow-hidden rounded-full bg-line"
          role="progressbar"
          aria-label="Lesson progress"
          aria-valuemin={0}
          aria-valuemax={exercises.length}
          aria-valuenow={answeredCount}
        >
          <div className="h-full rounded-full bg-primary transition-[width] duration-500 ease-out" style={{ width: `${progressPct}%` }}>
            <div className="mx-2 mt-1 h-1 rounded-full bg-white/30" />
          </div>
        </div>
        {attempt?.mode === "PRACTICE" && (
          <span className="hidden rounded-lg bg-primary-light px-2 py-1 text-xs font-black text-primary-ink uppercase sm:inline">
            Mistakes are free
          </span>
        )}
        <span className="flex items-center gap-1 text-lg font-black text-heart" aria-label={`${hearts ?? 0} hearts left`}>
          <HeartIcon key={hearts ?? 0} className="h-7 w-7 animate-pop" />
          {hearts ?? 0}
        </span>
      </header>

      <main data-exercise-area className="mx-auto w-full max-w-2xl flex-1 px-4 py-8 sm:py-12">
        {exercise && (
          <div key={exercise.id} className="animate-slide-in">
            <ExerciseRenderer
              exercise={exercise}
              language={{ code: meta.language_code, name: meta.course_title }}
              disabled={phase !== "ANSWERING"}
              status={status}
              onAnswerChange={(next) => dispatch({ type: "ANSWER_CHANGED", answer: next })}
              onAutoSubmit={(auto) => void check(auto)}
            />
          </div>
        )}
      </main>

      {phase === "SUBMITTING" ? (
        <footer className="border-t-2 border-line">
          <div className="mx-auto flex max-w-3xl items-center justify-between gap-4 px-4 py-5 sm:py-7">
            <p className="font-bold text-muted" role="status">
              {state.error ? errorMessage(state.error) : "Saving your progress…"}
            </p>
            {state.error !== null && <Button onClick={() => void submit()}>Retry</Button>}
          </div>
        </footer>
      ) : (
        <FeedbackBar
          result={phase === "FEEDBACK" || phase === "OUT_OF_HEARTS" ? result : null}
          canCheck={answer !== null}
          checking={phase === "CHECKING"}
          onCheck={() => void check()}
          onContinue={next}
          errorMessage={state.error ? errorMessage(state.error) : null}
          exerciseIndex={index}
        />
      )}

      {phase === "OUT_OF_HEARTS" && <OutOfHeartsModal onRefilled={() => dispatch({ type: "REFILLED" })} />}

      {confirmQuit && (
        <Modal title="Quit lesson?" onClose={() => setConfirmQuit(false)}>
          <div className="flex flex-col items-center gap-2 text-center">
            <Mascot mood="sad" className="h-20 w-20" />
            <p className="text-xl font-black">Wait, don&apos;t go!</p>
            <p className="text-muted">You&apos;ll lose your progress in this lesson.</p>
          </div>
          <div className="mt-6 flex flex-col gap-3">
            <Button fullWidth onClick={() => setConfirmQuit(false)}>
              Keep learning
            </Button>
            <Button variant="ghost" fullWidth onClick={() => router.push("/")} className="text-danger">
              End session
            </Button>
          </div>
        </Modal>
      )}
    </div>
  );
}
