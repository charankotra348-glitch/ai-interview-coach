import re
from dataclasses import dataclass

from app.profiles.schemas import CandidateProfile, JobProfile

ALIASES = {
    "postgres": "postgresql",
    "js": "javascript",
    "ts": "typescript",
    "py": "python",
    "k8s": "kubernetes",
    "golang": "go",
    "node": "node.js",
    "nodejs": "node.js",
    "reactjs": "react",
    "react.js": "react",
    "amazon web services": "aws",
    "gcp": "google cloud",
    "google cloud platform": "google cloud",
    "microsoft azure": "azure",
    "sklearn": "scikit-learn",
    "torch": "pytorch",
    "tf": "tensorflow",
    "ml": "machine learning",
}

# A requirement naming a category is satisfied by any member of it.
CATEGORIES = {
    "cloud": {"aws", "google cloud", "azure"},
    "cloud platform": {"aws", "google cloud", "azure"},
    "cloud platforms": {"aws", "google cloud", "azure"},
    "deep learning frameworks": {"pytorch", "tensorflow", "keras", "jax"},
    "ml frameworks": {"pytorch", "tensorflow", "keras", "jax", "scikit-learn"},
    "relational databases": {"postgresql", "mysql", "sqlite", "sql server", "oracle"},
    "sql": {"postgresql", "mysql", "sqlite", "sql server", "oracle"},   # every one of them is used through SQL    
    "containerization": {"docker", "kubernetes", "podman"},
}

SPLIT = re.compile(r"\s+or\s+|\s*/\s*", re.IGNORECASE)


def canonical(skill: str) -> str:
    s = " ".join(skill.lower().split()).strip(" .,;")
    return ALIASES.get(s, s)


def variants(skill: str) -> set[str]:
    """The skill itself plus its parts: 'PyTorch or TensorFlow' -> both; 'CI/CD' -> ci/cd, ci, cd."""
    out = {canonical(skill)}
    out.update(canonical(part) for part in SPLIT.split(skill) if part.strip())
    out.discard("")
    return out


def satisfying_skill(requirement: str, have: set[str]) -> str | None:
    options = variants(requirement)
    for option in list(options):
        options |= CATEGORIES.get(option, set())
    for option in sorted(options):
        if option in have:
            return option
    return None


@dataclass(frozen=True)
class Match:
    requirement: str  # as written in the job description
    via: str          # the candidate skill that satisfies it


@dataclass(frozen=True)
class SkillGap:
    matched: list[Match]
    missing_required: list[str]
    missing_nice_to_have: list[str]
    coverage: float | None  # share of required skills met; None if the job lists none


def _unique_requirements(skills: list[str]) -> list[str]:
    seen, out = set(), []
    for s in skills:
        key = canonical(s)
        if key and key not in seen:
            seen.add(key)
            out.append(s)
    return out


def compute_gap(candidate: CandidateProfile, job: JobProfile) -> SkillGap:
    have: set[str] = set()
    for skill in candidate.skills:
        have |= variants(skill)
    for project in candidate.projects:
        for tech in project.technologies:
            have |= variants(tech)

    required = _unique_requirements(job.required_skills)
    matched, missing = [], []
    for req in required:
        via = satisfying_skill(req, have)
        if via:
            matched.append(Match(requirement=req, via=via))
        else:
            missing.append(req)

    missing_nice = [
        req for req in _unique_requirements(job.nice_to_have_skills)
        if not satisfying_skill(req, have)
    ]
    return SkillGap(
        matched=matched,
        missing_required=missing,
        missing_nice_to_have=missing_nice,
        coverage=round(len(matched) / len(required), 2) if required else None,
    )