"use client";

import type { AnswerResult } from "@/lib/types";

import { Button } from "../ui/Button";
import { CheckIcon, CloseIcon } from "../ui/icons";

const PRAISE = ["Nice!", "Great job!", "Excellent!", "¡Muy bien!", "Correct!"];

interface FeedbackBarProps {
  /** null while answering: shows the Check button. */
  result: AnswerResult | null;
  canCheck: boolean;
  checking: boolean;
  onCheck: () => void;
  onContinue: () => void;
  errorMessage: string | null;
  exerciseIndex: number;
}

/** Footer that turns from a Check button into green/red feedback with Continue. */
export function FeedbackBar({
  result,
  canCheck,
  checking,
  onCheck,
  onContinue,
  errorMessage,
  exerciseIndex,
}: FeedbackBarProps) {
  const tone = result === null ? "border-line bg-white" : result.correct ? "border-transparent bg-primary-light" : "border-transparent bg-danger-light";

  return (
    <footer className={`border-t-2 transition-colors ${tone}`}>
      <div className="mx-auto flex max-w-3xl flex-col gap-4 px-4 py-5 sm:flex-row sm:items-center sm:justify-between sm:py-7">
        <div aria-live="polite" className="min-h-0 flex-1">
          {result && (
            <div className="flex animate-fade-in items-start gap-4">
              <span
                className={`grid h-14 w-14 shrink-0 place-items-center rounded-full bg-white ${result.correct ? "text-primary" : "text-danger"}`}
                aria-hidden="true"
              >
                {result.correct ? <CheckIcon className="h-8 w-8" /> : <CloseIcon className="h-8 w-8" />}
              </span>
              <div className={result.correct ? "text-primary-dark" : "text-danger-dark"}>
                <p className="text-2xl font-black">{result.correct ? PRAISE[exerciseIndex % PRAISE.length] : "Correct answer:"}</p>
                {!result.correct && result.correct_answer && <p className="text-lg font-bold">{result.correct_answer}</p>}
                {result.note && <p className="mt-1 font-bold">{result.note}</p>}
                {result.explanation && <p className="mt-1 text-sm font-semibold opacity-90">{result.explanation}</p>}
              </div>
            </div>
          )}
          {!result && errorMessage && (
            <p role="alert" className="font-bold text-danger">
              {errorMessage}
            </p>
          )}
        </div>

        {result ? (
          <Button variant={result.correct ? "primary" : "danger"} onClick={onContinue} className="sm:min-w-44">
            Continue
          </Button>
        ) : (
          <Button onClick={onCheck} disabled={!canCheck || checking} className="sm:min-w-44">
            {checking ? "Checking…" : "Check"}
          </Button>
        )}
      </div>
    </footer>
  );
}
