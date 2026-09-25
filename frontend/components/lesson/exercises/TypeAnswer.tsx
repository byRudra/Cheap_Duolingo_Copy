"use client";

import { useId, useRef, useState } from "react";

import type { ExerciseProps } from "./types";

/** On-screen keys for characters that are awkward to type on an English keyboard. */
const SPECIAL_CHARACTERS: Record<string, string[]> = {
  es: ["á", "é", "í", "ó", "ú", "ñ", "ü", "¿", "¡"],
  fr: ["é", "è", "ê", "à", "â", "ç", "ô", "û", "ù", "î", "ï", "ë", "œ"],
};

export function TypeAnswer({ exercise, language, disabled, status, onAnswerChange }: ExerciseProps<"TYPE_ANSWER">) {
  const specialCharacters = SPECIAL_CHARACTERS[language.code] ?? [];
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [text, setText] = useState("");

  function update(value: string) {
    setText(value);
    onAnswerChange(value.trim() ? { text: value } : null);
  }

  function insert(char: string) {
    const input = inputRef.current;
    if (!input) return;
    const start = input.selectionStart ?? text.length;
    const end = input.selectionEnd ?? text.length;
    update(text.slice(0, start) + char + text.slice(end));
    requestAnimationFrame(() => {
      input.focus();
      input.setSelectionRange(start + char.length, start + char.length);
    });
  }

  const tone =
    status === "correct"
      ? "border-primary bg-primary-light"
      : status === "incorrect"
        ? "border-danger bg-danger-light animate-shake"
        : "border-line bg-surface focus:border-secondary";

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-black sm:text-3xl">{exercise.prompt}</h1>
      <div className="flex flex-col gap-2">
        <label htmlFor={inputId} className="font-bold text-muted">
          Your answer in {language.name}
        </label>
        <input
          ref={inputRef}
          id={inputId}
          type="text"
          value={text}
          disabled={disabled}
          autoFocus
          autoComplete="off"
          autoCapitalize="off"
          spellCheck={false}
          lang={language.code}
          placeholder={exercise.payload.placeholder ?? `Type in ${language.name}`}
          onChange={(event) => update(event.target.value)}
          className={`min-h-14 w-full rounded-2xl border-2 px-4 text-xl font-bold outline-none transition-colors ${tone}`}
        />
      </div>
      {specialCharacters.length > 0 && (
      <div className="flex flex-wrap gap-2" role="group" aria-label="Insert special character">
        {specialCharacters.map((char) => (
          <button
            key={char}
            type="button"
            disabled={disabled}
            onClick={() => insert(char)}
            aria-label={`Insert ${char}`}
            className="grid h-11 min-w-11 place-items-center rounded-xl border-2 border-b-4 border-line bg-card text-lg font-bold hover:bg-surface"
          >
            {char}
          </button>
        ))}
      </div>
      )}
    </div>
  );
}
