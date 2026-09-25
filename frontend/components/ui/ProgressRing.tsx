interface ProgressRingProps {
  /** 0–100 */
  progress: number;
  size: number;
  stroke: number;
  color: string;
  trackColor?: string;
  className?: string;
  children?: React.ReactNode;
}

export function ProgressRing({
  progress,
  size,
  stroke,
  color,
  trackColor = "var(--color-line)",
  className = "",
  children,
}: ProgressRingProps) {
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.min(100, Math.max(0, progress));
  return (
    <div className={`relative inline-grid place-items-center ${className}`} style={{ width: size, height: size }}>
      <svg width={size} height={size} className="absolute inset-0 -rotate-90" aria-hidden="true">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke={trackColor} strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - clamped / 100)}
          className="transition-[stroke-dashoffset] duration-700 ease-out"
        />
      </svg>
      <div className="relative">{children}</div>
    </div>
  );
}
