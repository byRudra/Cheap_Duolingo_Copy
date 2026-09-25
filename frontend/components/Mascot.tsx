// "Pico", Habla's original parrot mascot, drawn from simple shapes.

type Mood = "happy" | "cheer" | "sad";

interface MascotProps {
  mood?: Mood;
  className?: string;
  label?: string;
}

export function Mascot({ mood = "happy", className = "h-24 w-24", label }: MascotProps) {
  const decorative = label === undefined;
  return (
    <svg
      viewBox="0 0 120 120"
      className={className}
      role={decorative ? undefined : "img"}
      aria-hidden={decorative ? true : undefined}
      aria-label={label}
    >
      {/* tail feathers */}
      <path d="M52 96 40 116l14-6 6 8 4-20Z" fill="#1fa5ea" />
      <path d="M62 96 66 118l8-10 10 4-14-18Z" fill="#ffb91f" />
      {/* wings */}
      <ellipse
        cx={mood === "cheer" ? 22 : 28}
        cy={mood === "cheer" ? 52 : 70}
        rx="12"
        ry="22"
        fill="#36962a"
        transform={mood === "cheer" ? "rotate(35 22 52)" : "rotate(12 28 70)"}
      />
      <ellipse
        cx={mood === "cheer" ? 98 : 92}
        cy={mood === "cheer" ? 52 : 70}
        rx="12"
        ry="22"
        fill="#36962a"
        transform={mood === "cheer" ? "rotate(-35 98 52)" : "rotate(-12 92 70)"}
      />
      {/* body */}
      <ellipse cx="60" cy="66" rx="34" ry="38" fill="#46b936" />
      <ellipse cx="60" cy="78" rx="21" ry="22" fill="#d7f5cf" />
      {/* crest */}
      <path d="M50 30c-2-12 4-20 10-22-1 7 3 10 4 14 3-6 9-8 13-7-5 4-6 10-7 15Z" fill="#ef4444" />
      {/* eyes */}
      <circle cx="46" cy="52" r="11" fill="#fff" />
      <circle cx="74" cy="52" r="11" fill="#fff" />
      {mood === "sad" ? (
        <>
          {/* downcast pupils + worried brows (inner ends raised) */}
          <circle cx="46" cy="57" r="5" fill="#2b3440" />
          <circle cx="74" cy="57" r="5" fill="#2b3440" />
          <path d="M35 42 52 36" stroke="#2b3440" strokeWidth="3.5" strokeLinecap="round" />
          <path d="M85 42 68 36" stroke="#2b3440" strokeWidth="3.5" strokeLinecap="round" />
        </>
      ) : (
        <>
          <circle cx="48" cy="53" r="5.5" fill="#2b3440" />
          <circle cx="72" cy="53" r="5.5" fill="#2b3440" />
          <circle cx="50" cy="51" r="1.8" fill="#fff" />
          <circle cx="74" cy="51" r="1.8" fill="#fff" />
        </>
      )}
      {/* beak */}
      <path d="M52 62h16c0 7-4 13-8 15-4-2-8-8-8-15Z" fill="#ffb91f" />
      {mood !== "sad" && <path d="M55 67q5 4 10 0" stroke="#d99a0b" strokeWidth="2.5" fill="none" strokeLinecap="round" />}
      {/* cheeks */}
      <circle cx="36" cy="66" r="4" fill="#ff4b6e" opacity=".35" />
      <circle cx="84" cy="66" r="4" fill="#ff4b6e" opacity=".35" />
    </svg>
  );
}
