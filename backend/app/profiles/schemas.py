from typing import Literal

from pydantic import BaseModel, field_validator

SENIORITY = ("intern", "junior", "mid", "senior", "unknown")
PLACEHOLDERS = {
    "unknown", "n/a", "na", "none", "null", "not specified",
    "not mentioned", "not stated", "various", "-", "tbd",
}


def clip(value, limit: int) -> str:
    if value is None:
        return ""
    text = " ".join(str(value).split())[:limit]
    return "" if text.lower() in PLACEHOLDERS else text


def clip_list(values, max_items: int, max_len: int) -> list[str]:
    """Trim, de-duplicate case-insensitively, and cap the list length."""
    out, seen = [], set()
    for value in values or []:
        text = clip(value, max_len)
        if text and text.lower() not in seen:
            seen.add(text.lower())
            out.append(text)
        if len(out) == max_items:
            break
    return out


class Project(BaseModel):
    name: str
    summary: str = ""
    technologies: list[str] = []

    @field_validator("name", mode="before")
    @classmethod
    def _name(cls, v):
        return clip(v, 80) or "Untitled project"

    @field_validator("summary", mode="before")
    @classmethod
    def _summary(cls, v):
        return clip(v, 300)

    @field_validator("technologies", mode="before")
    @classmethod
    def _tech(cls, v):
        return clip_list(v, 10, 40)


class Role(BaseModel):
    title: str
    organization: str = ""
    summary: str = ""

    @field_validator("title", mode="before")
    @classmethod
    def _title(cls, v):
        return clip(v, 80) or "Untitled role"

    @field_validator("organization", mode="before")
    @classmethod
    def _org(cls, v):
        return clip(v, 80)

    @field_validator("summary", mode="before")
    @classmethod
    def _summary(cls, v):
        return clip(v, 300)


class CandidateProfile(BaseModel):
    """Deliberately has no name, email, phone or links: unknown keys are dropped."""

    headline: str = ""
    skills: list[str] = []
    projects: list[Project] = []
    roles: list[Role] = []
    education: list[str] = []

    @field_validator("headline", mode="before")
    @classmethod
    def _headline(cls, v):
        return clip(v, 120)

    @field_validator("skills", mode="before")
    @classmethod
    def _skills(cls, v):
        return clip_list(v, 30, 40)

    @field_validator("projects", mode="before")
    @classmethod
    def _projects(cls, v):
        return (v or [])[:6]

    @field_validator("roles", mode="before")
    @classmethod
    def _roles(cls, v):
        return (v or [])[:5]

    @field_validator("education", mode="before")
    @classmethod
    def _education(cls, v):
        return clip_list(v, 3, 150)


class JobProfile(BaseModel):
    title: str = ""
    company: str = ""
    seniority: Literal["intern", "junior", "mid", "senior", "unknown"] = "unknown"
    required_skills: list[str] = []
    nice_to_have_skills: list[str] = []
    other_requirements: list[str] = []
    responsibilities: list[str] = []

    @field_validator("title", "company", mode="before")
    @classmethod
    def _short(cls, v):
        return clip(v, 120)

    @field_validator("seniority", mode="before")
    @classmethod
    def _seniority(cls, v):
        v = clip(v, 20).lower()
        return v if v in SENIORITY else "unknown"

    @field_validator("required_skills", "nice_to_have_skills", mode="before")
    @classmethod
    def _skills(cls, v):
        return clip_list(v, 20, 60)

    @field_validator("other_requirements", "responsibilities", mode="before")
    @classmethod
    def _lists(cls, v):
        return clip_list(v, 8, 200)