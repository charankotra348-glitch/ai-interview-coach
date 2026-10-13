import re

from app.profiles.schemas import CandidateProfile, JobProfile
from app.profiles.skills import SPLIT


def _norm(text: str) -> str:
    # Case, spaces and punctuation are ignored: "Scikit-learn" matches "scikit learn".
    return re.sub(r"[^a-z0-9+#]", "", text.lower())


def is_grounded(value: str, source_norm: str) -> bool:
    """True if the value, or one of its alternatives, appears in the source text."""
    parts = [value] + [p for p in SPLIT.split(value) if p.strip()]
    return any(_norm(p) and _norm(p) in source_norm for p in parts)


def _filter(values: list[str], source_norm: str) -> tuple[list[str], list[str]]:
    kept, dropped = [], []
    for v in values:
        (kept if is_grounded(v, source_norm) else dropped).append(v)
    return kept, dropped


def ground_candidate(profile: CandidateProfile, source: str) -> tuple[CandidateProfile, list[str]]:
    src = _norm(source)
    skills, dropped = _filter(profile.skills, src)
    projects = []
    for project in profile.projects:
        tech, d = _filter(project.technologies, src)
        dropped += d
        projects.append(project.model_copy(update={"technologies": tech}))
    return profile.model_copy(update={"skills": skills, "projects": projects}), dropped


def ground_job(profile: JobProfile, source: str) -> tuple[JobProfile, list[str]]:
    src = _norm(source)
    required, d1 = _filter(profile.required_skills, src)
    nice, d2 = _filter(profile.nice_to_have_skills, src)
    updated = profile.model_copy(update={"required_skills": required, "nice_to_have_skills": nice})
    return updated, d1 + d2