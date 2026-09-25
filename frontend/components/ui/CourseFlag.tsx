/**
 * Course badge. Windows can't render flag emoji (it shows letters like "ES"),
 * so known languages get an inline SVG; others fall back to the emoji.
 * Punjabi is a language of two countries, so it gets a Gurmukhi letter tile
 * instead of a national flag.
 */
const LANGUAGE_NAMES: Record<string, string> = {
  es: "Spanish",
  fr: "French",
  pa: "Punjabi",
  en: "English",
};

export function languageName(code: string): string {
  return LANGUAGE_NAMES[code] ?? code.toUpperCase();
}

export function CourseFlag({ code, emoji, className = "h-6 w-8" }: { code?: string; emoji?: string; className?: string }) {
  const label = code ? languageName(code) : "Course language";
  const common = { viewBox: "0 0 30 20", className: `${className} shrink-0 rounded-md`, role: "img", "aria-label": label } as const;
  switch (code) {
    case "es":
      return (
        <svg {...common}>
          <rect width="30" height="20" fill="#c60b1e" />
          <rect y="5" width="30" height="10" fill="#ffc400" />
        </svg>
      );
    case "fr":
      return (
        <svg {...common}>
          <rect width="10" height="20" fill="#0055a4" />
          <rect x="10" width="10" height="20" fill="#ffffff" />
          <rect x="20" width="10" height="20" fill="#ef4135" />
        </svg>
      );
    case "en":
      return (
        <svg {...common}>
          <rect width="30" height="20" fill="#012169" />
          <path d="M0 0 30 20M30 0 0 20" stroke="#fff" strokeWidth="4" />
          <path d="M0 0 30 20M30 0 0 20" stroke="#c8102e" strokeWidth="1.6" />
          <path d="M15 0v20M0 10h30" stroke="#fff" strokeWidth="6" />
          <path d="M15 0v20M0 10h30" stroke="#c8102e" strokeWidth="3.4" />
        </svg>
      );
    case "pa":
      return (
        <svg {...common}>
          <rect width="30" height="20" fill="#f28c28" />
          <text x="15" y="15.5" textAnchor="middle" fontSize="14" fontWeight="700" fill="#ffffff">
            ੳ
          </text>
        </svg>
      );
    default:
      return (
        <span role="img" aria-label={label} className="text-2xl">
          {emoji}
        </span>
      );
  }
}
