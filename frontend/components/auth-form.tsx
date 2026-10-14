"use client";

import Link from "next/link";
import { useState } from "react";
import { ApiError, postJson, safeNext } from "@/lib/api";

type Mode = "login" | "register";

export function AuthForm({ mode }: { mode: Mode }) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    const form = new FormData(event.currentTarget);
    const credentials = { email: String(form.get("email")), password: String(form.get("password")) };
    try {
      if (mode === "register") await postJson("/api/auth/register", credentials);
      await postJson("/api/auth/login", credentials);
      const next = new URLSearchParams(window.location.search).get("next");
      window.location.assign(safeNext(next));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not reach the server.");
      setBusy(false);
    }
  }

  const title = mode === "login" ? "Log in" : "Create your account";
  return (
    <main className="flex flex-1 items-center justify-center px-4">
      <form onSubmit={onSubmit} className="w-full max-w-sm space-y-4 rounded-xl border border-black/10 p-6 dark:border-white/15">
        <h1 className="text-2xl font-semibold">{title}</h1>
        <label className="block space-y-1">
          <span className="text-sm">Email</span>
          <input name="email" type="email" required autoComplete="email"
                 className="w-full rounded-md border border-black/15 bg-transparent px-3 py-2 dark:border-white/20" />
        </label>
        <label className="block space-y-1">
          <span className="text-sm">Password</span>
          <input name="password" type="password" required minLength={mode === "register" ? 12 : 1} maxLength={128}
                 autoComplete={mode === "login" ? "current-password" : "new-password"}
                 className="w-full rounded-md border border-black/15 bg-transparent px-3 py-2 dark:border-white/20" />
          {mode === "register" && <span className="text-xs opacity-70">At least 12 characters.</span>}
        </label>
        {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
        <button type="submit" disabled={busy}
                className="w-full rounded-md bg-foreground px-3 py-2 font-medium text-background disabled:opacity-50">
          {busy ? "Please wait..." : title}
        </button>
        <p className="text-center text-sm">
          {mode === "login"
            ? <>No account yet? <Link href="/register" className="underline">Create one</Link></>
            : <>Already registered? <Link href="/login" className="underline">Log in</Link></>}
        </p>
      </form>
    </main>
  );
}