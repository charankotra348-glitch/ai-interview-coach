"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { DIFFICULTY_NAMES, MODE_NAMES } from "@/lib/interview";
import type { Session, Summary } from "@/lib/types";
import { ErrorNote, button } from "@/components/ui";
import { ScoreBar } from "@/components/score-bar";

async function loadSummary(id: string) {
  const [session, summary] = await Promise.all([
    api<Session>(`/api/backend/sessions/${id}`),
    api<Summary>(`/api/backend/sessions/${id}/summary`),
  ]);
  return { session, summary };
}

export function SummaryScreen() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<{ session: Session; summary: Summary } | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    let current = true;
    loadSummary(id)
      .then((d) => { if (current) setData(d); })
      .catch((e) => { if (current) setError(e); });
    return () => { current = false; };
  }, [id]);

  const s = data?.summary;
  const session = data?.session;
  const criteria = s ? Object.entries(s.criteria_averages) : [];
  const delta = s?.follow_up_target_delta;

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-8 sm:px-6">
      <Link href="/dashboard" className={button.link}>Dashboard</Link>
      <ErrorNote error={error} onRetry={() => loadSummary(id).then(setData).catch(setError)} />
      {!data && !error && <p className="mt-8 text-pencil" aria-live="polite">Loading your summary...</p>}

      {s && session && (
        <>
          <h1 className="mt-8 text-2xl font-semibold tracking-tight">{MODE_NAMES[session.mode]} interview summary</h1>
          <p className="text-pencil">{session.target_role}</p>

          <p className="mt-8 flex items-baseline gap-2">
            <span className="text-6xl font-semibold tabular-nums">{s.average_overall ?? "–"}</span>
            <span className="text-pencil">average out of 10, across {s.answered - s.follow_ups} main questions</span>
          </p>

          {criteria.length > 0 && (
            <section aria-labelledby="criteria" className="mt-10">
              <h2 id="criteria" className="font-semibold">By criterion</h2>
              <p className="text-sm text-pencil">Average score from 1 to 5. Your lowest is where to practise next.</p>
              <div className="mt-4 space-y-3">
                {criteria.map(([name, score]) => <ScoreBar key={name} label={name} score={score} />)}
              </div>
            </section>
          )}

          <section aria-labelledby="adaptive" className="mt-10 space-y-2 text-sm">
            <h2 id="adaptive" className="text-base font-semibold">How the interview adapted</h2>
            <p>
              Difficulty by question:{" "}
              {s.difficulty_path.map((d, i) => (
                <span key={i}>{i > 0 && ", "}{DIFFICULTY_NAMES[d] ?? d}</span>
              ))}.
            </p>
            <p>
              {s.follow_ups === 0
                ? "No follow-ups were needed."
                : `${s.follow_ups} follow-up${s.follow_ups > 1 ? "s" : ""} probed a weak point.`}
              {delta !== null && delta !== undefined &&
                ` On the targeted criterion, your follow-up answers scored ${delta >= 0 ? "+" : ""}${delta} points compared with the original answer.`}
            </p>
          </section>

          <section aria-labelledby="questions" className="mt-10">
            <h2 id="questions" className="font-semibold">Questions</h2>
            <ol className="mt-3 divide-y divide-rule">
              {session.questions.map((q) => (
                <li key={q.id} className="flex items-baseline justify-between gap-4 py-3 text-sm">
                  <span>{q.is_follow_up && <span className="text-pencil">Follow-up: </span>}{q.text}</span>
                  <span className="shrink-0 tabular-nums">{q.evaluation ? `${q.evaluation.overall}/10` : "Not answered"}</span>
                </li>
              ))}
            </ol>
          </section>

          {s.llm_calls > 0 && <p className="mt-10 text-xs text-pencil">
            This interview used {s.llm_calls} AI call{s.llm_calls === 1 ? "" : "s"} and {(s.llm_latency_ms / 1000).toFixed(1)} seconds of model time,
            at an estimated cost of ${s.estimated_cost_usd}
            {s.calls_without_cost > 0 && ` (${s.calls_without_cost} call${s.calls_without_cost > 1 ? "s" : ""} had no price, for example a local model)`}.
          </p>}

          <Link href="/dashboard" className={`${button.primary} mt-8 inline-block`}>Start another interview</Link>
        </>
      )}
    </main>
  );
}