import Link from "next/link";
import type { Mode, SessionItem } from "@/lib/types";

const MODE_NAMES: Record<Mode, string> = {
  behavioral: "Behavioral",
  project: "Projects",
  system_design: "System design",
};

const dateFormat = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" });

export function InterviewList({ sessions }: { sessions: SessionItem[] }) {
  if (sessions.length === 0) {
    return <p className="text-sm text-pencil">Your interviews will be listed here, with a summary for each one you finish.</p>;
  }
  return (
    <ul className="divide-y divide-rule">
      {sessions.map((s) => {
        const done = s.status === "completed";
        return (
          <li key={s.id}>
            <Link href={done ? `/interview/${s.id}/summary` : `/interview/${s.id}`}
                  className="flex items-baseline justify-between gap-3 py-3 hover:text-accent">
              <span>
                <span className="block font-medium">{MODE_NAMES[s.mode]}</span>
                <span className="block text-sm text-pencil">{s.target_role}</span>
              </span>
              <span className="text-right text-sm text-pencil">
                <span className="block tabular-nums">{done ? "Finished" : `${s.answered} of ${s.max_questions} answered`}</span>
                <span className="block">{dateFormat.format(new Date(s.created_at))}</span>
              </span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}