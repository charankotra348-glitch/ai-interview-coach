"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, postJson } from "@/lib/api";

type Me = { id: string; email: string };

export default function DashboardPage() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);

  useEffect(() => {
    api<Me>("/api/backend/auth/me").then(setMe).catch(() => {});
  }, []);

  async function logout() {
    await postJson("/api/auth/logout", {});
    router.replace("/login");
  }

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 space-y-6 px-4 py-10">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <div className="flex items-center gap-4 text-sm">
          <span className="opacity-70">{me ? me.email : "Loading..."}</span>
          <button onClick={logout} className="rounded-md border border-black/15 px-3 py-1 dark:border-white/20">
            Log out
          </button>
        </div>
      </header>
      <p className="opacity-80">
        You are signed in. Uploading your resume and starting an interview come next (Step 8b).
      </p>
    </main>
  );
}