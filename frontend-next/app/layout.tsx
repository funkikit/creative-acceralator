import "../styles/globals.css";
import type { Metadata } from "next";
import { Noto_Sans_JP } from "next/font/google";

const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
const notoSans = Noto_Sans_JP({ subsets: ["latin"], display: "swap" });

export const metadata: Metadata = {
  title: "Creative Gen Studio",
  description: "PoC creative workflow with persona validation",
  icons: {
    icon: `${apiBase}/static/favicon.ico`,
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ja" className="bg-slate-950">
      <body className={notoSans.className}>{children}</body>
    </html>
  );
}
