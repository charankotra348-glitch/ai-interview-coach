import type { ReactNode } from "react";
import { ApiError } from "@/lib/api";

/** One numbered step of the prep sheet. The numbers are a real order: resume, job, start. */
export function Step({ n, title, hint, done, children }: {
  n: number; title: string; hint: string; done?: boolean; children: ReactNode;
}) {
  return (
    <section aria-labelledby={`step-${n}`} className="border-t border-rule pt-6">
      <div className="flex items-baseline gap-3">
        <span aria-hidden className={`grid size-7 shrink-0 place-items-center rounded-full text-sm font-semibold tabular-nums
          ${done ? "bg-ink text-paper" : "border border-rule text-pencil"}`}>{n}</span>
        <div>
          <h2 id={`step-${n}`} className="text-lg font-semibold">{title}</h2>
          <p className="text-sm text-pencil">{hint}</p>
        </div>
      </div>
      <div className="mt-4 pl-10">{children}</div>
    </section>
  );
}

export function ErrorNote({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  if (!error) return null;
  const message = error instanceof ApiError ? error.message : "Could not reach the server.";
  const retryable = error instanceof ApiError ? error.retryable : true;
  return (
    <p role="alert" className="mt-3 text-sm text-warn">
      {message}{" "}
      {retryable && onRetry && <button onClick={onRetry} className="underline">Try again</button>}
    </p>
  );
}

export const button = {
  primary: "rounded-md bg-accent px-4 py-2 font-medium text-accent-ink disabled:opacity-50",
  secondary: "rounded-md border border-rule bg-surface px-3 py-1.5 text-sm disabled:opacity-50",
  link: "text-sm text-pencil underline underline-offset-2 hover:text-ink",
};