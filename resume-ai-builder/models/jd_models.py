"""Pydantic models for JD analysis, matching and retrieval ranking."""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

MatchStatus = Literal["MATCH", "PARTIAL", "NOT_FOUND"]
Importance = Literal["required", "preferred"]


class JobDescriptionAnalysis(BaseModel):
    job_title: str = ""
    company: str = ""
    raw_text: str = ""
    required_skills: List[str] = Field(default_factory=list)
    preferred_skills: List[str] = Field(default_factory=list)
    skills_by_category: Dict[str, List[str]] = Field(default_factory=dict)
    responsibilities: List[str] = Field(default_factory=list)
    soft_skills: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    experience_requirements: List[str] = Field(default_factory=list)
    education_requirements: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    min_years_experience: Optional[float] = None

    @property
    def all_skills(self) -> List[str]:
        seen = {s.lower() for s in self.required_skills}
        return self.required_skills + [s for s in self.preferred_skills if s.lower() not in seen]


class SkillMatch(BaseModel):
    skill: str
    status: MatchStatus
    importance: Importance = "required"
    method: str = ""
    evidence: str = ""


class MatchResult(BaseModel):
    skill_matches: List[SkillMatch] = Field(default_factory=list)
    overall_alignment: float = 0.0
    required_matched: int = 0
    required_partial: int = 0
    required_total: int = 0
    preferred_matched: int = 0
    preferred_partial: int = 0
    preferred_total: int = 0
    keyword_coverage: float = 0.0
    text_similarity: float = 0.0
    experience_relevance: float = 0.0
    project_relevance: float = 0.0
    matched_keywords: List[str] = Field(default_factory=list)
    missing_keywords: List[str] = Field(default_factory=list)

    def by_status(self, status: MatchStatus) -> List[SkillMatch]:
        return [m for m in self.skill_matches if m.status == status]

    @property
    def matched_skills(self) -> List[str]:
        return [m.skill for m in self.by_status("MATCH")]

    @property
    def partial_skills(self) -> List[str]:
        return [m.skill for m in self.by_status("PARTIAL")]

    @property
    def missing_skills(self) -> List[str]:
        return [m.skill for m in self.by_status("NOT_FOUND")]


class RankedItem(BaseModel):
    ref_id: str
    item_type: str
    title: str
    score: float = 0.0
    text_score: float = 0.0
    matched_skills: List[str] = Field(default_factory=list)


class ResumeRanking(BaseModel):
    experience: List[RankedItem] = Field(default_factory=list)
    projects: List[RankedItem] = Field(default_factory=list)
    certifications: List[RankedItem] = Field(default_factory=list)
    achievements: List[RankedItem] = Field(default_factory=list)

    def score_of(self, ref_id: str) -> float:
        for items in (self.experience, self.projects, self.certifications, self.achievements):
            for item in items:
                if item.ref_id == ref_id:
                    return item.score
        return 0.0
