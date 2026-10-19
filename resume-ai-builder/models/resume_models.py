"""Pydantic models for the Master Resume (source of truth) and tailored resumes."""

from __future__ import annotations

import uuid
from typing import Dict, List

from pydantic import BaseModel, Field

from utils.skill_dictionary import SKILL_CATEGORIES


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _join(*parts: str) -> str:
    return "\n".join(p for p in parts if p and p.strip())


class PersonalInfo(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    github: str = ""
    portfolio: str = ""

    def contact_items(self) -> List[str]:
        return [v for v in (self.email, self.phone, self.location, self.linkedin,
                            self.github, self.portfolio) if v and v.strip()]


class SkillSet(BaseModel):
    programming_languages: List[str] = Field(default_factory=list)
    ai_ml: List[str] = Field(default_factory=list)
    deep_learning: List[str] = Field(default_factory=list)
    nlp: List[str] = Field(default_factory=list)
    web_development: List[str] = Field(default_factory=list)
    frameworks: List[str] = Field(default_factory=list)
    databases: List[str] = Field(default_factory=list)
    cloud: List[str] = Field(default_factory=list)
    devops: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)
    other: List[str] = Field(default_factory=list)

    def get(self, category: str) -> List[str]:
        return list(getattr(self, category, []))

    def add(self, category: str, skill: str) -> None:
        if category not in SKILL_CATEGORIES:
            category = "other"
        current: List[str] = getattr(self, category)
        if skill and skill.lower() not in {s.lower() for s in self.all_skills()}:
            current.append(skill)

    def all_skills(self) -> List[str]:
        seen: set[str] = set()
        result: List[str] = []
        for category in SKILL_CATEGORIES:
            for skill in getattr(self, category):
                if skill and skill.lower() not in seen:
                    seen.add(skill.lower())
                    result.append(skill)
        return result

    def as_labeled_dict(self) -> Dict[str, List[str]]:
        return {label: list(getattr(self, key)) for key, label in SKILL_CATEGORIES.items()
                if getattr(self, key)}


class Experience(BaseModel):
    id: str = Field(default_factory=lambda: new_id("exp"))
    company: str = ""
    title: str = ""
    location: str = ""
    start_date: str = ""
    end_date: str = ""
    description: str = ""
    bullets: List[str] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)

    def text(self) -> str:
        return _join(self.title, self.company, self.description, "\n".join(self.bullets),
                     ", ".join(self.technologies))

    def display_title(self) -> str:
        parts = [p for p in (self.title, self.company) if p]
        return " — ".join(parts) or "Untitled role"


class Project(BaseModel):
    id: str = Field(default_factory=lambda: new_id("proj"))
    name: str = ""
    description: str = ""
    technologies: List[str] = Field(default_factory=list)
    responsibilities: List[str] = Field(default_factory=list)
    results: str = ""
    achievements: List[str] = Field(default_factory=list)

    def text(self) -> str:
        return _join(self.name, self.description, "\n".join(self.responsibilities), self.results,
                     "\n".join(self.achievements), ", ".join(self.technologies))

    def display_title(self) -> str:
        return self.name or "Untitled project"


class Education(BaseModel):
    id: str = Field(default_factory=lambda: new_id("edu"))
    degree: str = ""
    institution: str = ""
    location: str = ""
    start_date: str = ""
    end_date: str = ""
    gpa: str = ""

    def text(self) -> str:
        return _join(self.degree, self.institution, self.location, self.gpa)

    def display_title(self) -> str:
        parts = [p for p in (self.degree, self.institution) if p]
        return " — ".join(parts) or "Untitled education"


class Certification(BaseModel):
    id: str = Field(default_factory=lambda: new_id("cert"))
    name: str = ""
    issuer: str = ""
    date: str = ""
    credential: str = ""

    def text(self) -> str:
        return _join(self.name, self.issuer)

    def display_title(self) -> str:
        parts = [p for p in (self.name, self.issuer) if p]
        return " — ".join(parts) or "Untitled certification"


class Achievement(BaseModel):
    id: str = Field(default_factory=lambda: new_id("ach"))
    title: str = ""
    description: str = ""

    def text(self) -> str:
        return _join(self.title, self.description)

    def display_title(self) -> str:
        return self.title or "Untitled achievement"


class MasterResume(BaseModel):
    """The single source of truth for every candidate fact."""

    personal: PersonalInfo = Field(default_factory=PersonalInfo)
    summary: str = ""
    skills: SkillSet = Field(default_factory=SkillSet)
    experience: List[Experience] = Field(default_factory=list)
    projects: List[Project] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    certifications: List[Certification] = Field(default_factory=list)
    achievements: List[Achievement] = Field(default_factory=list)

    def is_empty(self) -> bool:
        return not any([
            self.personal.name.strip(), self.summary.strip(), self.skills.all_skills(),
            self.experience, self.projects, self.education, self.certifications,
            self.achievements,
        ])

    def full_text(self) -> str:
        sections = [
            self.personal.name,
            self.summary,
            ", ".join(self.skills.all_skills()),
            *[e.text() + f"\n{e.location} {e.start_date} {e.end_date}" for e in self.experience],
            *[p.text() for p in self.projects],
            *[e.text() + f"\n{e.start_date} {e.end_date}" for e in self.education],
            *[c.text() + f"\n{c.date} {c.credential}" for c in self.certifications],
            *[a.text() for a in self.achievements],
        ]
        return _join(*sections)


class SkillGroup(BaseModel):
    category: str
    skills: List[str] = Field(default_factory=list)


class TailoredResume(BaseModel):
    """A job-specific resume built only from Master Resume facts."""

    personal: PersonalInfo = Field(default_factory=PersonalInfo)
    summary: str = ""
    skills: List[SkillGroup] = Field(default_factory=list)
    experience: List[Experience] = Field(default_factory=list)
    projects: List[Project] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    certifications: List[Certification] = Field(default_factory=list)
    achievements: List[Achievement] = Field(default_factory=list)
    target_job_title: str = ""
    target_company: str = ""
    generation_mode: str = "local"

    def all_skills(self) -> List[str]:
        return [s for group in self.skills for s in group.skills]

    def narrative_text(self) -> str:
        """Free-text content where fabricated claims could hide."""
        return _join(
            self.summary,
            *[_join(e.description, "\n".join(e.bullets)) for e in self.experience],
            *[_join(p.description, "\n".join(p.responsibilities), p.results,
                    "\n".join(p.achievements)) for p in self.projects],
            *[a.description for a in self.achievements],
        )
