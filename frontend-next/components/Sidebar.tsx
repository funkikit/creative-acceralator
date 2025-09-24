"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import clsx from "clsx";
import { useTransition } from "react";

const NAV_ITEMS = [
  { href: "/creative", label: "クリエイティブ" },
  { href: "/evaluation", label: "エージェント評価" },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  const handleLogout = async () => {
    startTransition(async () => {
      await fetch("/api/auth/logout", { method: "POST" });
      router.push("/login");
      router.refresh();
    });
  };

  return (
    <aside className="hidden w-64 flex-col bg-slate-950/80 p-6 border-r border-white/10 lg:flex">
      <div className="mb-8">
        <span className="inline-flex items-center rounded-full bg-gradient-to-r from-primary-500 to-primary-300 px-3 py-1 text-xs font-semibold text-slate-950">
          PoC モード
        </span>
        <p className="mt-4 text-sm text-slate-300">
          限定公開中。API 利用のコスト管理に注意してください。
        </p>
      </div>
      <nav className="flex-1 space-y-1">
        {NAV_ITEMS.map((item) => {
          const active = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                "block rounded-xl px-4 py-3 text-sm font-semibold transition",
                active
                  ? "bg-gradient-to-r from-primary-500 to-primary-400 text-slate-950 shadow-lg shadow-primary-500/30"
                  : "text-slate-300 hover:bg-white/5 hover:text-white"
              )}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
      <button
        onClick={handleLogout}
        disabled={pending}
        className="mt-8 inline-flex items-center justify-center rounded-xl border border-white/10 px-4 py-2 text-sm text-slate-300 transition hover:bg-white/5"
      >
        ログアウト
      </button>
    </aside>
  );
}
