"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { postJson } from "@/lib/api";
import type { Mode } from "@/lib/types";
import { ErrorNote, Step, button } from "@/components/ui";

const MODES: { value: Mode; label: string; about: string }[] = [
  { value: "behavioral", label: "Behavioral", about: "Ownership, conflict, failure: told as stories." },
  { value: "project", label: "Your projects", about: "Deep questions about what you built and why." },
  { value: "system_design", label: "System design", about: "Design a service, scoped for an internship." },
];

export function StartStep({ candidateId, jobId }: { candidateId: string | null; jobId: string | null }) {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("behavioral");
  const [questions, setQuestions] = useState(5);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function start() {
    setBusy(true);
    setError(null);
    try {
      const session = await postJson<{ id: string }>("/api/backend/sessions", {
        mode,
        max_questions: questions,
        candidate_profile_id: candidateId,
        job_profile_id: jobId,
      });
      router.push(`/interview/${session.id}`);
    } catch (e) {
      setError(e);
      setBusy(false);
    }
  }

  const needsResume = mode === "project" && !candidateId;
  return (
    <Step n={3} title="Start an interview" hint="Questions adapt as you go: a weak answer gets one follow-up, a strong one raises the difficulty.">
      <fieldset>
        <legend className="sr-only">Interview type</legend>
        <div className="grid gap-2 sm:grid-cols-3">
          {MODES.map((m) => (
            <label key={m.value}
                   className={`cursor-pointer rounded-md border p-3 text-sm has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-accent
                     ${mode === m.value ? "border-ink bg-surface" : "border-rule"}`}>
              <input type="radio" name="mode" value={m.value} checked={mode === m.value}
                     onChange={() => setMode(m.value)} className="sr-only" />
              <span className="block font-medium">{m.label}</span>
              <span className="block text-pencil">{m.about}</span>
            </label>
          ))}
        </div>
      </fieldset>
      <div className="mt-4 flex flex-wrap items-center gap-4">
        <label className="flex items-center gap-2 text-sm">
          Questions
          <input type="number" min={1} max={10} value={questions}
                 onChange={(e) => setQuestions(Math.min(10, Math.max(1, Number(e.target.value) || 1)))}
                 className="w-16 rounded-md border border-rule bg-surface px-2 py-1 tabular-nums" />
        </label>
        <button onClick={start} disabled={busy || needsResume} className={button.primary}>
          {busy ? "Starting..." : "Start interview"}
        </button>
        {needsResume && <span className="text-sm text-pencil">Project interviews need your resume first.</span>}
      </div>
      <ErrorNote error={error} onRetry={start} />
    </Step>
  );
}