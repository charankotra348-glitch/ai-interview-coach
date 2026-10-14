/** A 1-to-5 score as a thin bar on a full-width track, with the number beside it. */
export function ScoreBar({ label, score, max = 5 }: { label: string; score: number; max?: number }) {
  const percent = Math.max(0, Math.min(100, (score / max) * 100));
  const shown = Number.isInteger(score) ? score : score.toFixed(1);
  return (
    <div className="grid grid-cols-[8.5rem_1fr_2.5rem] items-center gap-3 text-sm" title={`${label}: ${shown} out of ${max}`}>
      <span className="truncate">{label}</span>
      <span className="h-2 rounded-full bg-rule" role="meter" aria-label={label}
            aria-valuemin={0} aria-valuemax={max} aria-valuenow={score}>
        <span className="block h-2 rounded-full bg-chart" style={{ width: `${percent}%` }} />
      </span>
      <span className="text-right tabular-nums text-pencil">{shown}/{max}</span>
    </div>
  );
}