import type { Metadata, Viewport } from "next";
import { Nunito } from "next/font/google";

import { UserStatsProvider } from "@/context/UserStatsContext";

import "./globals.css";

const nunito = Nunito({
  variable: "--font-nunito",
  subsets: ["latin", "latin-ext"],
  weight: ["400", "600", "700", "800", "900"],
});

export const metadata: Metadata = {
  title: "Habla · Learn Spanish",
  description: "Bite-sized, gamified Spanish lessons with streaks, hearts and XP.",
};

export const viewport: Viewport = {
  themeColor: "#46b936",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${nunito.variable} h-full`}>
      <body className="min-h-full">
        <UserStatsProvider>{children}</UserStatsProvider>
      </body>
    </html>
  );
}
