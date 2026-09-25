"use client";

import { useState } from "react";

import { OptionCard } from "./OptionCard";
import type { ExerciseProps } from "./types";
import { useNumberKeys } from "./useNumberKeys";

export function MultipleChoice({ exercise, disabled, status, onAnswerChange }: ExerciseProps<"MULTIPLE_CHOICE">) {
  const { options } = exercise.payload;
  const [selected, setSelected] = useState<number | null>(null);

  function pick(index: number) {
    setSelected(index);
    onAnswerChange({ answer: options[index] });
  }

  useNumberKeys(options.length, disabled, pick);

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-black sm:text-3xl">{exercise.prompt}</h1>
      <div role="group" aria-label="Answer options" className="grid gap-3 sm:grid-cols-2">
        {options.map((option, index) => (
          <OptionCard
            key={option}
            label={option}
            hotkey={index + 1}
            selected={selected === index}
            disabled={disabled}
            status={status}
            onSelect={() => pick(index)}
          />
        ))}
      </div>
    </div>
  );
}
