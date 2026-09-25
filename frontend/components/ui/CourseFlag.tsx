/**
 * Course flag. Windows can't render flag emoji (it shows the letters "ES"),
 * so known languages get an inline SVG; others fall back to the emoji.
 */
export function CourseFlag({ code, emoji, className = "h-6 w-8" }: { code?: string; emoji?: string; className?: string }) {
  if (code === "es") {
    return (
      <svg viewBox="0 0 30 20" className={`${className} rounded-md`} role="img" aria-label="Spanish">
        <rect width="30" height="20" fill="#c60b1e" />
        <rect y="5" width="30" height="10" fill="#ffc400" />
      </svg>
    );
  }
  return (
    <span role="img" aria-label="Course language" className="text-2xl">
      {emoji}
    </span>
  );
}
