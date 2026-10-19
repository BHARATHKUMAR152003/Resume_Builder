"""Compare a JD against the Master Resume: skill matching and alignment scores."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel
from rapidfuzz import fuzz, process
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from models.jd_models import JobDescriptionAnalysis, MatchResult, ResumeRanking, SkillMatch
from models.resume_models import MasterResume
from services.retriever import rank_resume
from utils.helpers import contains_phrase
from utils.logger import get_logger
from utils.skill_dictionary import SKILL_CATEGORIES, extract_skills, normalize_skill, related_skills

logger = get_logger("matcher")

FUZZY_THRESHOLD = 88
TEXT_SIMILARITY_REFERENCE = 0.40
WEIGHTS = {
    "required": 0.40, "preferred": 0.10, "keywords": 0.20,
    "text": 0.10, "experience": 0.10, "projects": 0.10,
}


class InventoryEntry(BaseModel):
    name: str
    original: str
    evidence: str


def build_skill_inventory(resume: MasterResume) -> Dict[str, InventoryEntry]:
    """All skills evidenced anywhere in the resume, keyed by lower-cased name."""
    inventory: Dict[str, InventoryEntry] = {}

    def add(raw: str, evidence: str) -> None:
        raw = (raw or "").strip()
        if not raw:
            return
        name = normalize_skill(raw) or raw
        inventory.setdefault(name.lower(), InventoryEntry(name=name, original=raw, evidence=evidence))

    for key, label in SKILL_CATEGORIES.items():
        for skill in resume.skills.get(key):
            add(skill, f"Skills › {label}")
    for exp in resume.experience:
        where = f"Experience › {exp.display_title()}"
        for tech in exp.technologies:
            add(tech, where)
        for skill in extract_skills(exp.text()):
            add(skill, where)
    for project in resume.projects:
        where = f"Project › {project.display_title()}"
        for tech in project.technologies:
            add(tech, where)
        for skill in extract_skills(project.text()):
            add(skill, where)
    for label, text in [("Summary", resume.summary)] + \
            [(f"Certification › {c.display_title()}", c.text()) for c in resume.certifications] + \
            [(f"Achievement › {a.display_title()}", a.text()) for a in resume.achievements] + \
            [(f"Education › {e.display_title()}", e.text()) for e in resume.education]:
        for skill in extract_skills(text):
            add(skill, label)
    return inventory


def match_skill(skill: str, inventory: Dict[str, InventoryEntry],
                importance: str = "required") -> SkillMatch:
    key = skill.lower()
    entry = inventory.get(key)
    if entry:
        method = "exact" if entry.original.lower() == key else "alias"
        return SkillMatch(skill=skill, status="MATCH", importance=importance, method=method,
                          evidence=entry.evidence)
    for related in sorted(related_skills(skill)):
        rel = inventory.get(related.lower())
        if rel:
            return SkillMatch(skill=skill, status="PARTIAL", importance=importance,
                              method="related", evidence=f"Related skill: {rel.name} ({rel.evidence})")
    if len(key) >= 4 and inventory:
        candidates = [k for k in inventory if len(k) >= 4]
        best = process.extractOne(key, candidates, scorer=fuzz.ratio) if candidates else None
        if best and best[1] >= FUZZY_THRESHOLD:
            rel = inventory[best[0]]
            return SkillMatch(skill=skill, status="PARTIAL", importance=importance, method="fuzzy",
                              evidence=f"Similar to: {rel.name} ({rel.evidence})")
    return SkillMatch(skill=skill, status="NOT_FOUND", importance=importance, method="none",
                      evidence="Not found in Master Resume")


def text_similarity(a: str, b: str) -> float:
    """Raw TF-IDF cosine similarity between two documents."""
    if not a.strip() or not b.strip():
        return 0.0
    try:
        matrix = TfidfVectorizer(stop_words="english", sublinear_tf=True).fit_transform([a, b])
        return float(cosine_similarity(matrix[0], matrix[1])[0][0])
    except ValueError:
        return 0.0


def _ratio(matched: int, partial: int, total: int) -> Optional[float]:
    return (matched + 0.5 * partial) / total if total else None


def match_resume(jd: JobDescriptionAnalysis, resume: MasterResume,
                 ranking: Optional[ResumeRanking] = None) -> MatchResult:
    """Classify each JD skill as MATCH / PARTIAL / NOT_FOUND and compute alignment."""
    ranking = ranking or rank_resume(resume, jd)
    inventory = build_skill_inventory(resume)
    matches: List[SkillMatch] = [match_skill(s, inventory, "required") for s in jd.required_skills]
    matches += [match_skill(s, inventory, "preferred") for s in jd.preferred_skills]

    result = MatchResult(skill_matches=matches)
    for importance in ("required", "preferred"):
        subset = [m for m in matches if m.importance == importance]
        setattr(result, f"{importance}_total", len(subset))
        setattr(result, f"{importance}_matched", sum(m.status == "MATCH" for m in subset))
        setattr(result, f"{importance}_partial", sum(m.status == "PARTIAL" for m in subset))

    resume_text = resume.full_text().lower()
    for keyword in jd.keywords:
        canonical = normalize_skill(keyword)
        found = (canonical and canonical.lower() in inventory) or contains_phrase(resume_text, keyword)
        (result.matched_keywords if found else result.missing_keywords).append(keyword)
    keyword_ratio = len(result.matched_keywords) / len(jd.keywords) if jd.keywords else None

    raw_similarity = text_similarity(jd.raw_text, resume.full_text())
    text_ratio = min(1.0, raw_similarity / TEXT_SIMILARITY_REFERENCE) if resume.full_text() else None
    exp_ratio = max((i.score for i in ranking.experience), default=None)
    top_projects = [i.score for i in ranking.projects[:3]]
    proj_ratio = sum(top_projects) / len(top_projects) if top_projects else None

    components = {
        "required": _ratio(result.required_matched, result.required_partial, result.required_total),
        "preferred": _ratio(result.preferred_matched, result.preferred_partial,
                            result.preferred_total),
        "keywords": keyword_ratio, "text": text_ratio,
        "experience": exp_ratio, "projects": proj_ratio,
    }
    used = {k: v for k, v in components.items() if v is not None}
    weight_sum = sum(WEIGHTS[k] for k in used)
    overall = sum(WEIGHTS[k] * v for k, v in used.items()) / weight_sum if weight_sum else 0.0

    result.overall_alignment = round(overall * 100, 1)
    result.keyword_coverage = round((keyword_ratio or 0.0) * 100, 1)
    result.text_similarity = round((text_ratio or 0.0) * 100, 1)
    result.experience_relevance = round((exp_ratio or 0.0) * 100, 1)
    result.project_relevance = round((proj_ratio or 0.0) * 100, 1)
    return result
