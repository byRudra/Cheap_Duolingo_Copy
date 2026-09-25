"use client";

import { useEffect, useState } from "react";

function format(ms: number): string {
  const total = Math.max(0, Math.ceil(ms / 1000));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

/** Displays the time left until a server-provided timestamp. */
export function Countdown({ to }: { to: string }) {
  const target = new Date(to).getTime();
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  return <time dateTime={to}>{format(target - now)}</time>;
}
