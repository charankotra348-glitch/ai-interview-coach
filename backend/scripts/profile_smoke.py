import json
import sys
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

from app.ingest.extract import extract_text
from app.llm.factory import build_llm_client
from app.profiles.extractor import extract_candidate_profile, extract_job_profile
from app.profiles.skills import compute_gap

if len(sys.argv) != 3:
    sys.exit("usage: python -m scripts.profile_smoke RESUME_PATH JOB_PATH")

resume_path, job_path = (Path(p).expanduser() for p in sys.argv[1:])
client = build_llm_client()

resume = extract_text(resume_path.read_bytes(), filename=resume_path.name)
job = extract_text(job_path.read_bytes(), filename=job_path.name)

candidate = extract_candidate_profile(client, resume.text)
job_profile = extract_job_profile(client, job.text)
gap = compute_gap(candidate.profile, job_profile.profile)

print("=== candidate ===")
print(candidate.profile.model_dump_json(indent=2))
print("=== job ===")
print(job_profile.profile.model_dump_json(indent=2))
print("=== gap ===")
print(json.dumps(asdict(gap), indent=2))

calls = candidate.calls + job_profile.calls
cost = sum((c.cost.usd or Decimal(0)) for c in calls)
print(f"\nparse attempts: candidate={candidate.parse_attempts} job={job_profile.parse_attempts}")
print(f"dropped as ungrounded: candidate={candidate.dropped} job={job_profile.dropped}")
print(f"llm calls={len(calls)}  latency total={sum(c.latency_ms for c in calls):.0f}ms  "
      f"estimated cost=${cost}")