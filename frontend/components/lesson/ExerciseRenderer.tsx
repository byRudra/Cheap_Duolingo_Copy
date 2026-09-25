"use client";

import type { ComponentType } from "react";

import type { Exercise, ExerciseType } from "@/lib/types";

import { FillBlank } from "./exercises/FillBlank";
import { MatchPairs } from "./exercises/MatchPairs";
import { MultipleChoice } from "./exercises/MultipleChoice";
import { TypeAnswer } from "./exercises/TypeAnswer";
import type { ExerciseProps } from "./exercises/types";
import { WordBank } from "./exercises/WordBank";

/** type → component. Adding an exercise type = one component + one entry here. */
const REGISTRY: { [T in ExerciseType]: ComponentType<ExerciseProps<T>> } = {
  MULTIPLE_CHOICE: MultipleChoice,
  WORD_BANK: WordBank,
  MATCH_PAIRS: MatchPairs,
  FILL_BLANK: FillBlank,
  TYPE_ANSWER: TypeAnswer,
};

type RendererProps = Omit<ExerciseProps<ExerciseType>, "exercise"> & { exercise: Exercise };

export function ExerciseRenderer({ exercise, ...props }: RendererProps) {
  // The registry's mapped type guarantees component/exercise agreement per key.
  const Component = REGISTRY[exercise.type] as ComponentType<ExerciseProps<typeof exercise.type>>;
  // key: remount (fresh local state) for every exercise.
  return <Component key={exercise.id} exercise={exercise} {...props} />;
}
