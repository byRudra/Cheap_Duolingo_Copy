"use client";

import { useState } from "react";

import type { ExerciseProps } from "./types";

const TILE =
  "min-h-12 rounded-2xl border-2 border-b-4 border-line bg-white px-4 py-2 text-lg font-bold text-ink transition-transform active:translate-y-0.5 disabled:cursor-default";

export function WordBank({ exercise, disabled, status, onAnswerChange }: ExerciseProps<"WORD_BANK">) {
  const { tiles } = exercise.payload;
  // Indices into `tiles`, in the order the learner placed them.
  const [placed, setPlaced] = useState<number[]>([]);

  function update(next: number[]) {
    setPlaced(next);
    onAnswerChange(next.length ? { tiles: next.map((i) => tiles[i]) } : null);
  }

  const lineTone =
    status === "correct" ? "text-primary-dark" : status === "incorrect" ? "text-danger-dark animate-shake" : "";

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-black sm:text-3xl">{exercise.prompt}</h1>

      <div
        aria-label="Your answer"
        role="group"
        className={`flex min-h-32 flex-wrap content-start gap-2 border-y-2 border-line py-3 ${lineTone}`}
        style={{
          backgroundImage: "linear-gradient(to bottom, transparent 62px, var(--color-line) 62px, var(--color-line) 64px, transparent 64px)",
          backgroundSize: "100% 64px",
        }}
      >
        {placed.length === 0 && <span className="self-center px-1 text-muted">Tap the words below to build your answer</span>}
        {placed.map((tileIndex, position) => (
          <button
            key={tileIndex}
            type="button"
            disabled={disabled}
            className={`${TILE} animate-pop`}
            onClick={() => update(placed.filter((_, p) => p !== position))}
            aria-label={`Remove “${tiles[tileIndex]}”`}
          >
            {tiles[tileIndex]}
          </button>
        ))}
      </div>

      <div role="group" aria-label="Word bank" className="flex flex-wrap justify-center gap-2">
        {tiles.map((tile, index) => {
          const used = placed.includes(index);
          return used ? (
            // Placeholder keeps the gap where the tile was.
            <span key={index} aria-hidden="true" className={`${TILE} border-transparent bg-line text-transparent`}>
              {tile}
            </span>
          ) : (
            <button
              key={index}
              type="button"
              disabled={disabled}
              className={TILE}
              onClick={() => update([...placed, index])}
            >
              {tile}
            </button>
          );
        })}
      </div>
    </div>
  );
}
