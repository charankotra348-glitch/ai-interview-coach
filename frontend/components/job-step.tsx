"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { JobProfile, Stored } from "@/lib/types";
import { ErrorNote, Step, button } from "@/components/ui";

export function JobStep({ job, onSaved }: {
  job: Stored<JobProfile> | null;
  onSaved: (j: Stored<JobProfile>) => void;
}) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [replacing, setReplacing] = useState(false);

  async function save() {
    setBusy(true);
    setError(null);
    const form = new FormData();
    form.append("text", text);
    try {
      onSaved(await api<Stored<JobProfile>>("/api/backend/profiles/job", { method: "POST", body: form }));
      setText("");
      setReplacing(false);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  const p = job?.profile;
  return (
    <Step n={2} title="Target job" done={!!job}
          hint="Paste the posting you are preparing for. It decides which skills and systems come up.">
      {p && !replacing ? (
        <div className="space-y-1">
          <p className="font-medium">{p.title || "Untitled role"}{p.company && <span className="font-normal text-pencil"> at {p.company}</span>}</p>
          <p className="text-sm text-pencil">{p.required_skills.length} required skills, {p.nice_to_have_skills.length} nice to have</p>
          <button onClick={() => setReplacing(true)} className={button.link}>Use a different job</button>
        </div>
      ) : (
        <div className="space-y-2">
          <label className="block">
            <span className="sr-only">Job description</span>
            <textarea value={text} onChange={(e) => setText(e.target.value)} rows={6} disabled={busy}
                      placeholder="Paste the full job description here"
                      className="w-full rounded-md border border-rule bg-surface p-3 text-sm" />
          </label>
          <div className="flex items-center gap-3">
            <button onClick={save} disabled={busy || text.trim().length < 50} className={button.secondary}>
              {busy ? "Reading the job..." : "Save job"}
            </button>
            {text.trim().length > 0 && text.trim().length < 50 && <span className="text-xs text-pencil">Paste the whole posting, not just the title.</span>}
            {replacing && !busy && <button onClick={() => setReplacing(false)} className={button.link}>Keep the current job</button>}
          </div>
        </div>
      )}
      <ErrorNote error={error} />
    </Step>
  );
}