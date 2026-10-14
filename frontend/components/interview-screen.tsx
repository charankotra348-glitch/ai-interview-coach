"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ApiError, api, postJson } from "@/lib/api";
import {
  DIFFICULTY_NAMES, MAX_ANSWER_CHARS, MIN_ANSWER_CHARS, MODE_NAMES,
  explainRationale, pendingQuestion, secondsSince, stage, wordCount,
} from "@/lib/interview";
import type { Question, Session } from "@/lib/types";
import { ErrorNote, button } from "@/components/ui";
import { Feedback } from "@/components/feedback";

type Busy = "loading" | "asking" | "grading" | null;

const loadSession = (id: string) => api<Session>(`/api/backend/sessions/${id}`);

/** Ask the backend for the next question. Safe to repeat: it returns the same open question. */
async function withNextQuestion(session: Session): Promise<Session> {
  const q = await postJson<Question>(`/api/backend/sessions/${session.id}/questions`, {});
  return { ...session, questions: [...session.questions.filter((x) => x.id !== q.id), q] };
}

/** Load the interview, and fetch its next question if none is open yet. */
async function openInterview(id: string): Promise<Session> {
  const session = await loadSession(id);
  return stage(session) === "ask" ? withNextQuestion(session) : session;
}

export function InterviewScreen() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [session, setSession] = useState<Session | null>(null);
  const [reviewing, setReviewing] = useState<Question | null>(null);   // the answer just graded
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState<Busy>("loading");
  const [error, setError] = useState<unknown>(null);
  const shownAt = useRef(0);   // when the open question appeared, to time the answer

  useEffect(() => {
    let current = true;
    openInterview(id)
      .then((s) => { if (current) { shownAt.current = Date.now(); setSession(s); setBusy(null); } })
      .catch((e) => { if (current) { setError(e); setBusy(null); } });
    return () => { current = false; };
  }, [id]);

  const summaryUrl = `/interview/${id}/summary`;

  async function retryOpen() {
    setError(null);
    setBusy("loading");
    try {
      setSession(await openInterview(id));
      shownAt.current = Date.now();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  }

  async function submit() {
    const q = session && pendingQuestion(session);
    if (!session || !q || busy) return;
    setBusy("grading");
    setError(null);
    try {
      const graded = await postJson<Question>(`/api/backend/sessions/${session.id}/questions/${q.id}/answer`, {
        text: draft.trim(),
        duration_seconds: secondsSince(shownAt.current, Date.now()),
      });
      setSession(await loadSession(session.id));   // the interview may be finished now
      setReviewing(graded);
      setDraft("");
    } catch (e) {
      if (e instanceof ApiError && e.code === "already_answered") {
        const fresh = await loadSession(session.id);   // answered in another tab: show that grade
        setSession(fresh);
        setReviewing(fresh.questions.find((x) => x.id === q.id) ?? null);
      } else {
        setError(e);   // the answer stays in the box, so nothing is lost
      }
    } finally {
      setBusy(null);
    }
  }

  async function next() {
    if (!session) return;
    setBusy("asking");
    setError(null);
    try {
      setSession(await withNextQuestion(session));
      setReviewing(null);
      shownAt.current = Date.now();
    } catch (e) {
      if (e instanceof ApiError && e.code === "session_complete") router.push(summaryUrl);
      else setError(e);
    } finally {
      setBusy(null);
    }
  }

  const open = session && pendingQuestion(session);
  const current = reviewing ?? open;
  const earlier = session?.questions.filter((q) => q.evaluation && q.id !== reviewing?.id) ?? [];
  const tooShort = draft.trim().length < MIN_ANSWER_CHARS;

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-8 sm:px-6">
      <header className="flex items-baseline justify-between gap-4 text-sm">
        <Link href="/dashboard" className={button.link}>Dashboard</Link>
        {session && current && (
          <span className="tabular-nums text-pencil">Question {current.position} of {session.max_questions}</span>
        )}
      </header>

      <h1 className="mt-8 text-2xl font-semibold tracking-tight">
        {session ? `${MODE_NAMES[session.mode]} interview` : "Interview"}
      </h1>
      {session && <p className="text-pencil">{session.target_role}</p>}

      {busy === "loading" && <p className="mt-8 text-pencil" aria-live="polite">Preparing your interview...</p>}
      <ErrorNote error={error} onRetry={session ? (open ? submit : next) : retryOpen} />

      {current && (
        <article className="mt-8">
          <p className="flex flex-wrap gap-x-3 text-sm text-pencil">
            <span>{DIFFICULTY_NAMES[current.difficulty] ?? "Standard"}</span>
            {explainRationale(current.rationale) && <span>{explainRationale(current.rationale)}</span>}
          </p>
          <h2 className="mt-2 text-xl leading-snug font-medium">{current.text}</h2>
        </article>
      )}

      {open && !reviewing && (
        <form className="mt-6" onSubmit={(e) => { e.preventDefault(); submit(); }}>
          <label htmlFor="answer" className="sr-only">Your answer</label>
          <textarea id="answer" value={draft} onChange={(e) => setDraft(e.target.value)} rows={10}
                    maxLength={MAX_ANSWER_CHARS} disabled={busy === "grading"} autoFocus
                    onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit(); }}
                    placeholder="Answer as you would out loud: the situation, what you did, and what happened."
                    className="w-full rounded-md border border-rule bg-surface p-3 leading-relaxed" />
          <div className="mt-3 flex flex-wrap items-center gap-4">
            <button type="submit" disabled={tooShort || busy !== null} className={button.primary}>
              {busy === "grading" ? "Grading..." : "Submit answer"}
            </button>
            <span className="text-sm tabular-nums text-pencil">{wordCount(draft)} words</span>
            <span className="hidden text-sm text-pencil sm:inline">Cmd + Enter submits</span>
          </div>
          {busy === "grading" && (
            <p className="mt-3 text-sm" aria-live="polite">Grading your answer. This usually takes 5 to 15 seconds.</p>
          )}
        </form>
      )}

      {reviewing?.evaluation && (
        <div className="mt-6 space-y-6">
          <details className="text-sm">
            <summary className="cursor-pointer text-pencil">Your answer</summary>
            <p className="mt-2 whitespace-pre-wrap">{reviewing.answer}</p>
          </details>
          <Feedback evaluation={reviewing.evaluation} />
          {session?.status === "completed" ? (
            <Link href={summaryUrl} className={`${button.primary} inline-block`}>See your summary</Link>
          ) : (
            <button onClick={next} disabled={busy !== null} className={button.primary}>
              {busy === "asking" ? "Preparing the next question..." : "Next question"}
            </button>
          )}
        </div>
      )}

      {session && !current && busy === null && session.status !== "active" && (
        <div className="mt-8">
          <p>This interview is finished.</p>
          <Link href={summaryUrl} className={`${button.primary} mt-4 inline-block`}>See your summary</Link>
        </div>
      )}

      {earlier.length > 0 && (
        <section aria-labelledby="earlier" className="mt-12 border-t border-rule pt-6">
          <h2 id="earlier" className="font-semibold">Earlier in this interview</h2>
          <ul className="mt-3 space-y-2 text-sm">
            {earlier.map((q) => (
              <li key={q.id} className="flex items-baseline justify-between gap-4">
                <span>{q.is_follow_up && <span className="text-pencil">Follow-up: </span>}{q.text}</span>
                <span className="shrink-0 tabular-nums text-pencil">{q.evaluation?.overall}/10</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}