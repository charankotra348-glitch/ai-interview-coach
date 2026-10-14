"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { CandidateProfile, Stored } from "@/lib/types";
import { ErrorNote, Step, button } from "@/components/ui";

export function ResumeStep({ resume, onSaved }: {
  resume: Stored<CandidateProfile> | null;
  onSaved: (r: Stored<CandidateProfile>) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [replacing, setReplacing] = useState(false);

  async function upload(file: File) {
    setBusy(true);
    setError(null);
    const form = new FormData();
    form.append("file", file);
    try {
      onSaved(await api<Stored<CandidateProfile>>("/api/backend/profiles/candidate", { method: "POST", body: form }));
      setReplacing(false);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  const p = resume?.profile;
  return (
    <Step n={1} title="Your resume" done={!!resume}
          hint="Questions are built from your own projects and skills. Contact details are never stored.">
      {p && !replacing ? (
        <div className="space-y-3">
          {p.headline && <p className="font-medium">{p.headline}</p>}
          <p className="text-sm text-pencil">{p.skills.length} skills, {p.projects.length} projects
            {resume.truncated && " (your resume was long, so only the first part was read)"}</p>
          {p.projects.length > 0 && (
            <ul className="space-y-1 text-sm">
              {p.projects.slice(0, 4).map((project) => (
                <li key={project.name}><span className="font-medium">{project.name}</span>
                  {project.technologies.length > 0 && <span className="text-pencil">: {project.technologies.join(", ")}</span>}
                </li>
              ))}
            </ul>
          )}
          <button onClick={() => setReplacing(true)} className={button.link}>Upload a different resume</button>
        </div>
      ) : (
        <div>
          <label className="block">
            <span className="sr-only">Resume file</span>
            <input type="file" accept=".pdf,.docx,.txt" disabled={busy}
                   onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
                   className="block w-full text-sm file:mr-3 file:rounded-md file:border file:border-rule file:bg-surface file:px-3 file:py-1.5 file:text-ink" />
          </label>
          <p className="mt-2 text-xs text-pencil">PDF, Word or plain text, up to 5 MB.</p>
          {busy && <p className="mt-2 text-sm" aria-live="polite">Reading your resume. This usually takes 10 to 30 seconds.</p>}
          {replacing && !busy && <button onClick={() => setReplacing(false)} className={`${button.link} mt-2`}>Keep the current resume</button>}
        </div>
      )}
      <ErrorNote error={error} />
    </Step>
  );
}