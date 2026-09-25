import type { Metadata, Viewport } from "next";
import { Nunito } from "next/font/google";

import { UserStatsProvider } from "@/context/UserStatsContext";
import { APP_NAME, APP_TAGLINE } from "@/lib/brand";
import { THEME_INIT_SCRIPT } from "@/lib/theme";

import "./globals.css";

const nunito = Nunito({
  variable: "--font-nunito",
  subsets: ["latin", "latin-ext"],
  weight: ["400", "600", "700", "800", "900"],
});

export const metadata: Metadata = {
  title: { default: `${APP_NAME} · Learn a language`, template: `%s · ${APP_NAME}` },
  description: APP_TAGLINE,
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#46b936" },
    { media: "(prefers-color-scheme: dark)", color: "#0f1b21" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // The inline script sets data-theme before paint, so React must not fight it.
    <html lang="en" className={`${nunito.variable} h-full`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="min-h-full">
        <UserStatsProvider>{children}</UserStatsProvider>
      </body>
    </html>
  );
}
