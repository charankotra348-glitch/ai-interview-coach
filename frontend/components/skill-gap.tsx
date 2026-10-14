import type { Gap, JobProfile } from "@/lib/types";

/**
 * The job's required skills as you'd mark up a printed posting: highlighted where your
 * resume already covers them, outlined where it doesn't. The one bold element on the page.
 */
export function SkillGap({ gap, job }: { gap: Gap; job: JobProfile }) {
  const covered = new Map(gap.matched.map((m) => [m.requirement, m.via]));
  const percent = gap.coverage === null ? null : Math.round(gap.coverage * 100);

  return (
    <div className="rounded-lg border border-rule bg-surface p-5">
      <p className="text-sm text-pencil">
        {percent === null
          ? "This posting lists no required skills."
          : <>Your resume covers <span className="font-semibold tabular-nums text-ink">{percent}%</span> of the required skills.</>}
      </p>
      <ul className="mt-4 flex flex-wrap gap-2" aria-label="Required skills">
        {job.required_skills.map((skill) => {
          const via = covered.get(skill);
          const sameSkill = via?.toLowerCase() === skill.toLowerCase();
          return via ? (
            <li key={skill} className="rounded-sm bg-mark px-2 py-0.5 text-sm text-mark-ink"
                title={sameSkill ? "On your resume" : `Covered by ${via} on your resume`}>
              {skill}{!sameSkill && <span className="opacity-70"> via {via}</span>}
            </li>
          ) : (
            <li key={skill} className="rounded-sm border border-dashed border-pencil px-2 py-0.5 text-sm text-pencil">
              <span className="sr-only">Missing: </span>{skill}
            </li>
          );
        })}
      </ul>
      {gap.missing_required.length > 0 && (
        <p className="mt-4 text-sm text-pencil">
          Not on your resume yet: {gap.missing_required.join(", ")}. Worth preparing to talk about these.
        </p>
      )}
    </div>
  );
}