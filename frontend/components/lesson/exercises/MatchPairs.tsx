"use client";

import { useMemo, useRef, useState } from "react";

import { shuffledIndices } from "@/lib/shuffle";

import type { ExerciseProps } from "./types";

type Side = "left" | "right";

/**
 * Validated on the client for instant per-tap feedback (the pairs must be on
 * the client anyway). A mismatch shakes both cards and costs no heart; once
 * every pair is matched the exercise submits `{ completed: true }` itself.
 */
export function MatchPairs({ exercise, disabled, onAutoSubmit }: ExerciseProps<"MATCH_PAIRS">) {
  const { pairs } = exercise.payload;
  const leftOrder = useMemo(() => shuffledIndices(pairs.length, exercise.id * 7919 + 1), [pairs.length, exercise.id]);
  const rightOrder = useMemo(() => shuffledIndices(pairs.length, exercise.id * 104729 + 3), [pairs.length, exercise.id]);

  const [selected, setSelected] = useState<{ left: number | null; right: number | null }>({ left: null, right: null });
  const [matched, setMatched] = useState<Set<number>>(() => new Set());
  const [wrong, setWrong] = useState<{ left: number; right: number } | null>(null);
  const wrongTimer = useRef<number | null>(null);

  function choose(side: Side, pairIndex: number) {
    if (disabled || matched.has(pairIndex) || wrong) return;
    const next = { ...selected, [side]: selected[side] === pairIndex ? null : pairIndex };
    if (next.left === null || next.right === null) {
      setSelected(next);
      return;
    }
    if (next.left === next.right) {
      const done = new Set(matched).add(next.left);
      setMatched(done);
      setSelected({ left: null, right: null });
      if (done.size === pairs.length) onAutoSubmit({ completed: true });
    } else {
      setWrong({ left: next.left, right: next.right });
      setSelected({ left: null, right: null });
      if (wrongTimer.current) window.clearTimeout(wrongTimer.current);
      wrongTimer.current = window.setTimeout(() => setWrong(null), 450);
    }
  }

  function cardClass(side: Side, pairIndex: number): string {
    const base =
      "min-h-14 w-full rounded-2xl border-2 border-b-4 px-3 py-3 text-lg font-bold transition-all duration-300 disabled:cursor-default";
    if (matched.has(pairIndex)) return `${base} border-primary/40 bg-primary-light text-primary-dark opacity-50`;
    if (wrong && wrong[side] === pairIndex) return `${base} border-danger bg-danger-light text-danger-dark animate-shake`;
    if (selected[side] === pairIndex) return `${base} border-secondary bg-secondary-light text-secondary-dark`;
    return `${base} border-line bg-white text-ink hover:bg-surface`;
  }

  function column(side: Side, order: number[]) {
    return (
      <ul className="flex flex-col gap-3" aria-label={side === "left" ? "Spanish" : "English"}>
        {order.map((pairIndex) => {
          const label = pairs[pairIndex][side];
          const isMatched = matched.has(pairIndex);
          return (
            <li key={pairIndex}>
              <button
                type="button"
                disabled={disabled || isMatched}
                aria-pressed={selected[side] === pairIndex}
                aria-label={isMatched ? `${label}, matched` : label}
                onClick={() => choose(side, pairIndex)}
                className={cardClass(side, pairIndex)}
              >
                {label}
              </button>
            </li>
          );
        })}
      </ul>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-black sm:text-3xl">{exercise.prompt}</h1>
      <p className="sr-only" aria-live="polite">
        {matched.size} of {pairs.length} pairs matched
      </p>
      <div className="grid grid-cols-2 gap-3 sm:gap-6">
        {column("left", leftOrder)}
        {column("right", rightOrder)}
      </div>
    </div>
  );
}
