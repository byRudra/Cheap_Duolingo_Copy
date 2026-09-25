// Colored initial avatar used on the profile header and leaderboard rows.
// Decorative: the learner's name is always rendered as text next to it.

const INK = "#2b3440";
const WHITE = "#ffffff";

function channel(value: number): number {
  const c = value / 255;
  return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

function luminance(hex: string): number | null {
  const match = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!match) return null;
  const n = parseInt(match[1], 16);
  return 0.2126 * channel((n >> 16) & 255) + 0.7152 * channel((n >> 8) & 255) + 0.0722 * channel(n & 255);
}

/** Pick whichever of white or ink text contrasts more with the background. */
function textColorFor(background: string): string {
  const lum = luminance(background);
  if (lum === null) return WHITE;
  const onWhite = 1.05 / (lum + 0.05);
  const onInk = (lum + 0.05) / (0.033 + 0.05);
  return onWhite >= onInk ? WHITE : INK;
}

interface AvatarProps {
  name: string;
  color: string;
  /** Size and font-size classes, e.g. "h-11 w-11 text-lg". */
  className?: string;
}

export function Avatar({ name, color, className = "h-11 w-11 text-lg" }: AvatarProps) {
  const initial = Array.from(name.trim())[0]?.toUpperCase() ?? "?";
  return (
    <span
      aria-hidden="true"
      className={`inline-grid shrink-0 place-items-center rounded-full border-b-4 border-black/15 font-black select-none ${className}`}
      style={{ backgroundColor: color, color: textColorFor(color) }}
    >
      {initial}
    </span>
  );
}
