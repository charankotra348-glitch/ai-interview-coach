"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, postJson } from "@/lib/api";
import type { CandidateProfile, Gap, JobProfile, Me, SessionItem, Stored } from "@/lib/types";
import { ErrorNote, button } from "@/components/ui";
import { ResumeStep } from "@/components/resume-step";
import { JobStep } from "@/components/job-step";
import { SkillGap } from "@/components/skill-gap";
import { StartStep } from "@/components/start-step";
import { InterviewList } from "@/components/interview-list";

type Resume = Stored<CandidateProfile>;
type Job = Stored<JobProfile>;
type Dashboard = { me: Me; resume: Resume | null; job: Job | null; sessions: SessionItem[]; gap: Gap | null };

function fetchGap(resume: Resume | null, job: Job | null): Promise<Gap | null> {
  if (!resume || !job) return Promise.resolve(null);
  return api<Gap>(`/api/backend/profiles/gap?candidate_id=${resume.id}&job_id=${job.id}`).catch(() => null);
}

async function fetchDashboard(): Promise<Dashboard> {
  const [me, resumes, jobs, sessions] = await Promise.all([
    api<Me>("/api/backend/auth/me"),
    api<Resume[]>("/api/backend/profiles/candidate?limit=1"),
    api<Job[]>("/api/backend/profiles/job?limit=1"),
    api<SessionItem[]>("/api/backend/sessions?limit=20"),
  ]);
  const resume = resumes[0] ?? null;
  const job = jobs[0] ?? null;
  return { me, resume, job, sessions, gap: await fetchGap(resume, job) };
}

export default function DashboardPage() {
  const router = useRouter();
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    let current = true;
    fetchDashboard()
      .then((d) => { if (current) setData(d); })
      .catch((e) => { if (current) setError(e); });
    return () => { current = false; };   // ignore a late answer after leaving the page
  }, []);

  function retry() {
    setError(null);
    fetchDashboard().then(setData).catch(setError);
  }

  // A new resume or job changes the skill gap, so fetch it again right away.
  async function saveResume(resume: Resume) {
    setData((d) => d && { ...d, resume });
    const gap = await fetchGap(resume, data?.job ?? null);
    setData((d) => d && { ...d, gap });
  }

  async function saveJob(job: Job) {
    setData((d) => d && { ...d, job });
    const gap = await fetchGap(data?.resume ?? null, job);
    setData((d) => d && { ...d, gap });
  }

  async function logout() {
    await postJson("/api/auth/logout", {});
    router.replace("/login");
  }

  return (
    <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 sm:px-6">
      <header className="flex items-center justify-between gap-4">
        <p className="font-semibold">AI Interview Coach</p>
        <div className="flex items-center gap-3 text-sm">
          <span className="hidden text-pencil sm:inline">{data?.me.email}</span>
          <button onClick={logout} className={button.secondary}>Log out</button>
        </div>
      </header>

      <h1 className="mt-10 text-3xl font-semibold tracking-tight">Prepare for your next interview</h1>
      <ErrorNote error={error} onRetry={retry} />
      {!data && !error && <p className="mt-8 text-pencil" aria-live="polite">Loading your profile...</p>}

      {data && (
        <div className="mt-8 grid gap-10 lg:grid-cols-[minmax(0,1fr)_18rem]">
          <div className="space-y-8">
            <ResumeStep resume={data.resume} onSaved={saveResume} />
            <JobStep job={data.job} onSaved={saveJob} />
            {data.gap && data.job && <SkillGap gap={data.gap} job={data.job.profile} />}
            <StartStep candidateId={data.resume?.id ?? null} jobId={data.job?.id ?? null} />
          </div>
          <aside aria-labelledby="past" className="lg:border-l lg:border-rule lg:pl-8">
            <h2 id="past" className="text-lg font-semibold">Your interviews</h2>
            <div className="mt-2"><InterviewList sessions={data.sessions} /></div>
          </aside>
        </div>
      )}
    </main>
  );
}