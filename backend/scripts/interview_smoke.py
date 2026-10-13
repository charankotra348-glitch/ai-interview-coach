import sys
from decimal import Decimal
from pathlib import Path

from app.ingest.extract import extract_text
from app.interview.evaluation import evaluate_answer
from app.interview.focus import choose_focus
from app.interview.questions import generate_question
from app.llm.factory import build_llm_client
from app.profiles.extractor import extract_candidate_profile, extract_job_profile
from app.profiles.skills import compute_gap

MODES = ("behavioral", "project", "system_design")
if len(sys.argv) != 4 or sys.argv[3] not in MODES:
    sys.exit("usage: python -m scripts.interview_smoke RESUME JOB MODE "
             "(MODE: behavioral | project | system_design)")

resume_path, job_path = (Path(p).expanduser() for p in sys.argv[1:3])
mode = sys.argv[3]
client = build_llm_client()

print("Reading your resume and the job description...")
candidate = extract_candidate_profile(
    client, extract_text(resume_path.read_bytes(), filename=resume_path.name).text).profile
job = extract_job_profile(
    client, extract_text(job_path.read_bytes(), filename=job_path.name).text).profile
gap = compute_gap(candidate, job)

focus = choose_focus(mode, candidate, job, [])
question = generate_question(client, mode=mode, focus=focus,
                             target_role=job.title or "Software Engineering Intern",
                             job=job, gap=gap)
print(f"\nFocus: {focus.topic}\n\nQ: {question.value.question}\n")

print("Type your answer. Press Enter on an empty line to finish:")
lines = []
while True:
    line = input()
    if not line.strip():
        break
    lines.append(line)

evaluation = evaluate_answer(client, mode=mode, question=question.value.question,
                             answer="\n".join(lines))
ev = evaluation.value

print(f"\nOverall: {ev.overall}/10")
for item in ev.rubric:
    print(f"  {item.name:<18} {item.score}/5  {item.note}")
    if item.evidence:
        print(f"  {'':<18} evidence: \"{item.evidence}\"")
print("\nStrengths:", *[f"\n  - {s}" for s in ev.strengths])
print("Improve:", *[f"\n  - {s}" for s in ev.improvements])
print(f"\nLikely follow-up: {ev.follow_up_question}")
print(f"Ungrounded evidence quotes: {ev.ungrounded_evidence}")

for label, result in (("question", question), ("evaluation", evaluation)):
    cost = sum((c.cost.usd or Decimal(0)) for c in result.calls)
    latency = sum(c.latency_ms for c in result.calls)
    print(f"{label}: attempts={result.attempts} latency={latency:.0f}ms cost=${cost}")