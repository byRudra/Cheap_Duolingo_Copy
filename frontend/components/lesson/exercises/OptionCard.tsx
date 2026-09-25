import type { CheckStatus } from "./types";

interface OptionCardProps {
  label: string;
  hotkey: number;
  selected: boolean;
  disabled: boolean;
  status: CheckStatus;
  onSelect: () => void;
  compact?: boolean;
}

/** Large tappable option used by multiple choice and fill-in-the-blank. */
export function OptionCard({ label, hotkey, selected, disabled, status, onSelect, compact = false }: OptionCardProps) {
  let tone = "border-line bg-white text-ink hover:bg-surface";
  if (selected && status === "correct") tone = "border-primary bg-primary-light text-primary-dark animate-pulse-correct";
  else if (selected && status === "incorrect") tone = "border-danger bg-danger-light text-danger-dark animate-shake";
  else if (selected) tone = "border-secondary bg-secondary-light text-secondary-dark";

  return (
    <button
      type="button"
      onClick={onSelect}
      disabled={disabled}
      aria-pressed={selected}
      className={`flex min-h-14 w-full items-center gap-3 rounded-2xl border-2 border-b-4 px-4 text-left text-lg font-bold transition-colors disabled:cursor-default ${
        compact ? "justify-center py-2" : "py-3"
      } ${tone}`}
    >
      {hotkey <= 9 && (
        <kbd
          aria-hidden="true"
          className="hidden h-7 w-7 shrink-0 place-items-center rounded-lg border-2 border-current/30 font-sans text-sm font-extrabold opacity-70 sm:grid"
        >
          {hotkey}
        </kbd>
      )}
      <span>{label}</span>
    </button>
  );
}
