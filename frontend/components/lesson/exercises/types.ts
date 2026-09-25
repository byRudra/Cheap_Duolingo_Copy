import type { AnswerPayload, ExerciseOf, ExerciseType } from "@/lib/types";

/** The language being learned, e.g. { code: "fr", name: "French" }. */
export interface LessonLanguage {
  code: string;
  name: string;
}

/** Outcome of the last Check, used for per-option styling during FEEDBACK. */
export type CheckStatus = "idle" | "correct" | "incorrect";

export interface ExerciseProps<T extends ExerciseType> {
  exercise: ExerciseOf<T>;
  language: LessonLanguage;
  /** True while checking or showing feedback: inputs are locked. */
  disabled: boolean;
  status: CheckStatus;
  /** Report the current answer, or null when there is nothing to check yet. */
  onAnswerChange: (answer: AnswerPayload | null) => void;
  /** Ask the player to check immediately (match pairs finishes by itself). */
  onAutoSubmit: (answer: AnswerPayload) => void;
}
