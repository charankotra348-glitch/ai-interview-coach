import type { Evaluation } from "@/lib/types";
import { ScoreBar } from "@/components/score-bar";

/** The grade for one answer: overall score, each criterion with its evidence, then what to keep and change. */
export function Feedback({ evaluation }: { evaluation: Evaluation }) {
  return (
    <section aria-label="Feedback on your answer" className="rounded-lg border border-rule bg-surface p-5">
      <p className="flex items-baseline gap-2">
        <span className="text-4xl font-semibold tabular-nums">{evaluation.overall}</span>
        <span className="text-pencil">out of 10</span>
      </p>

      <ul className="mt-5 space-y-4">
        {evaluation.rubric.map((item) => (
          <li key={item.name}>
            <ScoreBar label={item.name} score={item.score} />
            {item.note && <p className="mt-1 text-sm text-pencil">{item.note}</p>}
            {item.evidence && (
              <blockquote className="mt-1 border-l-2 border-mark pl-3 text-sm italic">“{item.evidence}”</blockquote>
            )}
          </li>
        ))}
      </ul>

      <div className="mt-6 grid gap-6 sm:grid-cols-2">
        <div>
          <h3 className="font-semibold">Keep doing</h3>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
            {evaluation.strengths.map((s) => <li key={s}>{s}</li>)}
          </ul>
        </div>
        <div>
          <h3 className="font-semibold">Improve next time</h3>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
            {evaluation.improvements.map((s) => <li key={s}>{s}</li>)}
          </ul>
        </div>
      </div>

      {(evaluation.feedback_source === "derived" || evaluation.ungrounded_evidence > 0) && (
        <p className="mt-5 text-xs text-pencil">
          {evaluation.feedback_source === "derived" && "These notes were built from the scores, because the grader left them out. "}
          {evaluation.ungrounded_evidence > 0 &&
            `${evaluation.ungrounded_evidence} quote${evaluation.ungrounded_evidence > 1 ? "s" : ""} from the grader did not match your answer and ${evaluation.ungrounded_evidence > 1 ? "were" : "was"} removed.`}
        </p>
      )}
    </section>
  );
}