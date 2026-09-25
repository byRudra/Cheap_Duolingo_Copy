"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Mascot } from "../Mascot";
import { HomeIcon, SettingsIcon, TrophyIcon, UserIcon } from "../ui/icons";
import { StatPills } from "./StatPills";

const NAV = [
  { href: "/", label: "Learn", Icon: HomeIcon },
  { href: "/leaderboard", label: "Leaderboard", Icon: TrophyIcon },
  { href: "/profile", label: "Profile", Icon: UserIcon },
  { href: "/settings", label: "Settings", Icon: SettingsIcon },
] as const;

function isActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen lg:pl-64">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 hidden w-64 flex-col border-r-2 border-line px-4 py-6 lg:flex">
        <Link href="/" className="mb-8 flex items-center gap-2 px-3" aria-label="Habla home">
          <Mascot className="h-11 w-11" />
          <span className="text-3xl font-black tracking-tight text-primary">habla</span>
        </Link>
        <nav aria-label="Main" className="flex flex-col gap-2">
          {NAV.map(({ href, label, Icon }) => {
            const active = isActive(pathname, href);
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={`flex min-h-12 items-center gap-4 rounded-2xl border-2 px-4 py-2 text-sm font-extrabold tracking-wide uppercase transition-colors ${
                  active
                    ? "border-secondary/60 bg-secondary-light text-secondary"
                    : "border-transparent text-muted hover:bg-surface"
                }`}
              >
                <Icon className="h-7 w-7" />
                {label}
              </Link>
            );
          })}
        </nav>
      </aside>

      {/* Mobile top bar */}
      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b-2 border-line bg-white/95 px-4 backdrop-blur lg:hidden">
        <Link href="/" className="flex items-center gap-1" aria-label="Habla home">
          <Mascot className="h-9 w-9" />
          <span className="text-xl font-black text-primary">habla</span>
        </Link>
        <StatPills />
      </header>

      <main className="pb-24 lg:pb-10">{children}</main>

      {/* Mobile bottom tabs */}
      <nav
        aria-label="Main"
        className="fixed inset-x-0 bottom-0 z-30 flex h-16 items-stretch justify-around border-t-2 border-line bg-white lg:hidden"
      >
        {NAV.map(({ href, label, Icon }) => {
          const active = isActive(pathname, href);
          return (
            <Link
              key={href}
              href={href}
              aria-label={label}
              aria-current={active ? "page" : undefined}
              className={`flex min-w-16 flex-1 flex-col items-center justify-center gap-0.5 text-[11px] font-extrabold uppercase ${
                active ? "text-secondary" : "text-muted"
              }`}
            >
              <span className={`rounded-xl px-3 py-0.5 ${active ? "bg-secondary-light" : ""}`}>
                <Icon className="h-7 w-7" />
              </span>
              {label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
