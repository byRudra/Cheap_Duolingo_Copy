// Rank indicator: a drawn medal for the podium (1–3), a plain number otherwise.

const MEDALS: Record<number, { fill: string; rim: string; ribbon: string }> = {
  1: { fill: "var(--color-gold)", rim: "var(--color-gold-dark)", ribbon: "var(--color-danger)" },
  2: { fill: "#dfe4e9", rim: "#aab3bc", ribbon: "var(--color-secondary)" },
  3: { fill: "#e7a970", rim: "#b8773f", ribbon: "var(--color-primary)" },
};

export function RankBadge({ rank }: { rank: number }) {
  const medal = MEDALS[rank];
  return (
    <span className="grid w-10 shrink-0 place-items-center">
      <span className="sr-only">Rank {rank}</span>
      {medal ? (
        <svg viewBox="0 0 40 44" className="h-10 w-9" aria-hidden="true">
          <path d="M11 0h7l3 14h-7L11 0Z" fill={medal.ribbon} />
          <path d="M29 0h-7l-3 14h7l3-14Z" fill={medal.ribbon} opacity=".8" />
          <circle cx="20" cy="27" r="15" fill={medal.rim} />
          <circle cx="20" cy="26" r="13" fill={medal.fill} />
          <circle cx="20" cy="26" r="9.5" fill="none" stroke="#fff" strokeOpacity=".55" strokeWidth="1.5" />
          <text
            x="20"
            y="31"
            textAnchor="middle"
            fontSize="14"
            fontWeight="900"
            fill="var(--color-ink)"
            fontFamily="inherit"
          >
            {rank}
          </text>
        </svg>
      ) : (
        <span aria-hidden="true" className="text-lg font-extrabold text-muted">
          {rank}
        </span>
      )}
    </span>
  );
}
