import type { ReactNode } from "react";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { Sidebar } from "../../components/Sidebar";

const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
const headerIconSrc = `${apiBase}/static/icon.png`;

const COOKIE_NAME = "poc-auth";

export default function ProtectedLayout({ children }: { children: ReactNode }) {
  const auth = cookies().get(COOKIE_NAME)?.value;
  if (auth !== "ok") {
    redirect("/login");
  }

  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-100">
      <Sidebar />
      <main className="flex-1 overflow-y-auto bg-slate-950/80 px-10 py-8">
        <div className="mx-auto max-w-6xl space-y-6">
          <header className="flex items-center justify-between rounded-3xl border border-white/10 bg-white/5 px-6 py-4 shadow-lg shadow-primary-500/10">
            <div className="flex items-center gap-4">
              <img
                src={headerIconSrc}
                alt="Creation Acceralator icon"
                className="h-10 w-10 rounded-2xl border border-white/20 object-cover"
              />
              <span className="text-lg font-semibold text-white">Creation Acceralator</span>
            </div>
          </header>
          {children}
        </div>
      </main>
    </div>
  );
}
