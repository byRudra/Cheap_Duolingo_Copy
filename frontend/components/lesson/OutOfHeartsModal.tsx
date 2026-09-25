"use client";

import Link from "next/link";
import { useState } from "react";

import { useUserStats } from "@/context/UserStatsContext";
import { api, errorMessage } from "@/lib/api";

import { Mascot } from "../Mascot";
import { Button, buttonClasses } from "../ui/Button";
import { Countdown } from "../ui/Countdown";
import { GemIcon, HeartIcon } from "../ui/icons";
import { Modal } from "../ui/Modal";

export function OutOfHeartsModal({ onRefilled }: { onRefilled: () => void }) {
  const { me, refresh } = useUserStats();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cost = me?.refill_cost ?? 350;
  const gems = me?.gems ?? 0;

  async function refill() {
    setPending(true);
    setError(null);
    try {
      await api.refillHearts();
      await refresh();
      onRefilled();
    } catch (err) {
      setError(errorMessage(err));
      setPending(false);
    }
  }

  return (
    <Modal title="You ran out of hearts">
      <div className="flex flex-col items-center gap-2 text-center">
        <Mascot mood="sad" className="h-24 w-24" />
        <div className="flex gap-1 text-locked" aria-hidden="true">
          {Array.from({ length: me?.max_hearts ?? 5 }, (_, i) => (
            <HeartIcon key={i} className="h-7 w-7" />
          ))}
        </div>
        <p className="text-2xl font-black" aria-hidden="true">
          You ran out of hearts
        </p>
        <p className="text-muted">
          Refill now to keep learning, or come back later.
          {me?.next_heart_at && (
            <>
              {" "}
              Next free heart in <Countdown to={me.next_heart_at} />.
            </>
          )}
        </p>
      </div>
      <div className="mt-6 flex flex-col gap-3">
        <Button variant="secondary" fullWidth onClick={refill} disabled={pending || gems < cost}>
          {pending ? "Refilling…" : "Refill"} <GemIcon className="h-5 w-5" /> {cost}
        </Button>
        <p className="-mt-1 text-center text-sm font-bold text-muted">You have {gems} gems</p>
        <Button variant="outline" fullWidth disabled title="Coming soon">
          Practice · Coming soon
        </Button>
        <Link href="/" className={buttonClasses("ghost", "w-full")}>
          Return home
        </Link>
      </div>
      {error && (
        <p role="alert" className="mt-3 text-center font-bold text-danger">
          {error}
        </p>
      )}
    </Modal>
  );
}
