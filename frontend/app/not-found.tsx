import Link from "next/link";

import { Mascot } from "@/components/Mascot";
import { buttonClasses } from "@/components/ui/Button";

export default function NotFound() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 px-4 text-center">
      <Mascot mood="sad" className="h-28 w-28" />
      <h1 className="text-3xl font-black">¡Ay! Page not found</h1>
      <p className="text-muted">That page flew away. Let&apos;s get you back to your lessons.</p>
      <Link href="/" className={buttonClasses("primary")}>
        Back to learning
      </Link>
    </main>
  );
}
