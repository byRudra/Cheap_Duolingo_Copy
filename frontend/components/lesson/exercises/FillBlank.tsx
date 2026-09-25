"use client";

import { useState } from "react";

import { OptionCard } from "./OptionCard";
import type { ExerciseProps } from "./types";
import { useNumberKeys } from "./useNumberKeys";

export function FillBlank({ exercise, disabled, status, onAnswerChange }: ExerciseProps<"FILL_BLANK">) {
  const { sentence, options } = exercise.payload;
  const [selected, setSelected] = useState<number | null>(null);
  const [before, after] = sentence.split("___");

  function pick(index: number) {
    setSelected(index);
    onAnswerChange({ answer: options[index] });
  }

  useNumberKeys(options.length, disabled, pick);

  const blankTone =
    status === "correct"
      ? "border-primary text-primary-dark"
      : status === "incorrect"
        ? "border-danger text-danger-dark"
        : "border-secondary text-secondary-dark";

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-black sm:text-3xl">{exercise.prompt}</h1>
      <p className="rounded-2xl border-2 border-line px-5 py-6 text-2xl font-bold leading-relaxed" aria-live="polite">
        {before}
        <span
          className={`mx-1 inline-block min-w-24 border-b-4 px-2 text-center ${selected === null ? "border-line-dark text-transparent" : blankTone}`}
        >
          {selected === null ? "____" : options[selected]}
        </span>
        {after}
      </p>
      <div role="group" aria-label="Answer options" className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {options.map((option, index) => (
          <OptionCard
            key={option}
            label={option}
            hotkey={index + 1}
            selected={selected === index}
            disabled={disabled}
            status={status}
            onSelect={() => pick(index)}
            compact
          />
        ))}
      </div>
    </div>
  );
}
