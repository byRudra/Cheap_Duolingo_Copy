import { errorMessage } from "@/lib/api";

import { Mascot } from "../Mascot";
import { Button } from "./Button";

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-2xl bg-line/70 ${className}`} aria-hidden="true" />;
}

export function ErrorState({
  error,
  onRetry,
  title = "Hmm, that didn't load",
}: {
  error: unknown;
  onRetry?: () => void;
  title?: string;
}) {
  return (
    <div role="alert" className="mx-auto flex max-w-sm flex-col items-center gap-3 px-4 py-10 text-center">
      <Mascot mood="sad" className="h-24 w-24" />
      <h2 className="text-xl font-extrabold">{title}</h2>
      <p className="text-muted">{errorMessage(error)}</p>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}

export function EmptyState({ title, message }: { title: string; message: string }) {
  return (
    <div className="mx-auto flex max-w-sm flex-col items-center gap-3 px-4 py-10 text-center">
      <Mascot className="h-24 w-24" />
      <h2 className="text-xl font-extrabold">{title}</h2>
      <p className="text-muted">{message}</p>
    </div>
  );
}
