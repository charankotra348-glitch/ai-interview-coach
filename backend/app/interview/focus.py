import re
from dataclasses import dataclass

from app.profiles.schemas import CandidateProfile, JobProfile

BEHAVIORAL_TOPICS = [
    "taking ownership of a problem",
    "a disagreement with a teammate",
    "a failure and what you learned",
    "working with unclear requirements",
    "learning a new technology quickly",
    "prioritizing under a deadline",
]

SYSTEM_DESIGN_TOPICS = [
    "a URL shortener",
    "a rate limiter for a public API",
    "a document question-answering service",
    "a notification service",
    "a chat application",
    "a file upload and storage service",
]

PROJECT_ANGLES = [
    "the overall architecture and how its parts fit together",
    "one important design decision and the alternatives considered",
    "the hardest problem faced and how it was solved",
    "how the results were measured or evaluated",
    "what they would change if they rebuilt it today",
]

AI_ROLE = re.compile(r"\b(rag|retrieval|vector|llm|embedding)s?\b", re.IGNORECASE)


@dataclass(frozen=True)
class Focus:
    kind: str
    topic: str
    detail: str = ""
    angle: str = ""


def _next_unasked(pool: list[str], asked: set[str]) -> str:
    for topic in pool:
        if topic.lower() not in asked:
            return topic
    return pool[len(asked) % len(pool)]  # everything asked: cycle round


def choose_focus(mode: str, candidate: CandidateProfile | None,
                 job: JobProfile | None, asked_topics: list[str]) -> Focus:
    asked = {t.lower() for t in asked_topics}

    if mode == "project":
        angle = PROJECT_ANGLES[len(asked) % len(PROJECT_ANGLES)]
        projects = candidate.projects if candidate else []
        if not projects:
            return Focus("project", "the project you are proudest of", angle=angle)
        for project in projects:
            if project.name.lower() not in asked:
                break
        else:
            project = projects[len(asked) % len(projects)]
        detail = project.summary
        if project.technologies:
            detail += f" Technologies: {', '.join(project.technologies)}."
        return Focus("project", project.name, detail.strip(), angle)

    if mode == "system_design":
        pool = list(SYSTEM_DESIGN_TOPICS)
        if job:
            text = " ".join(job.required_skills + job.nice_to_have_skills + job.responsibilities)
            if AI_ROLE.search(text):
                # An AI role: ask about the most relevant system first.
                pool.remove("a document question-answering service")
                pool.insert(0, "a document question-answering service")
        return Focus("system", _next_unasked(pool, asked))

    return Focus("competency", _next_unasked(BEHAVIORAL_TOPICS, asked))