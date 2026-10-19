"""Deterministic, template-based tailored resume generation (no LLM).

Only selects, reorders and trims Master Resume content. Bullets are never
rewritten, so nothing can be fabricated.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel

from models.jd_models import JobDescriptionAnalysis, MatchResult, ResumeRanking
from models.resume_models import MasterResume, SkillGroup, TailoredResume
from services.resume_matcher import build_skill_inventory
from utils.helpers import join_human, tokenize
from utils.skill_dictionary import (
    SKILL_CATEGORIES,
    extract_skills,
    normalize_skill,
    related_skills,
    skill_category,
)

SELECTION_THRESHOLD = 0.10
DOMAIN_CATEGORIES = {"ai_ml", "deep_learning", "nlp", "web_development", "databases", "cloud",
                     "devops"}


class GenerationOptions(BaseModel):
    experience_ids: Optional[List[str]] = None
    project_ids: Optional[List[str]] = None
    certification_ids: Optional[List[str]] = None
    max_projects: int = 3
    max_bullets_per_role: int = 6
    include_achievements: bool = True


class Selection(BaseModel):
    experience_ids: List[str]
    project_ids: List[str]
    certification_ids: List[str]


def default_selection(resume: MasterResume, ranking: ResumeRanking,
                      max_projects: int = 3) -> Selection:
    """Pre-select the most relevant items; the user can change this in the UI."""
    relevant_exp = {i.ref_id for i in ranking.experience if i.score >= SELECTION_THRESHOLD}
    relevant_exp |= {i.ref_id for i in ranking.experience[:2]}
    experience_ids = [e.id for e in resume.experience if e.id in relevant_exp]

    top_score = ranking.projects[0].score if ranking.projects else 0.0
    project_ids = [
        i.ref_id for i in ranking.projects
        if i.score >= SELECTION_THRESHOLD and i.score >= 0.4 * top_score
    ][:max_projects]
    if not project_ids:
        project_ids = [i.ref_id for i in ranking.projects[:min(2, max_projects)]]

    cert_ids = [i.ref_id for i in ranking.certifications if i.score >= SELECTION_THRESHOLD]
    if not cert_ids:
        cert_ids = [c.id for c in resume.certifications[:5]]
    return Selection(experience_ids=experience_ids, project_ids=project_ids,
                     certification_ids=cert_ids)


def _jd_skill_rank(jd: JobDescriptionAnalysis) -> Dict[str, int]:
    return {s.lower(): i for i, s in enumerate(jd.all_skills)}


def _skill_sort_key(skill: str, index: int, jd_rank: Dict[str, int], jd_lower: set) -> tuple:
    canonical = (normalize_skill(skill) or skill)
    if canonical.lower() in jd_rank:
        return (0, jd_rank[canonical.lower()], index)
    if any(r.lower() in jd_lower for r in related_skills(canonical)):
        return (1, 0, index)
    return (2, 0, index)


def reorder_skills(resume: MasterResume, jd: JobDescriptionAnalysis) -> List[SkillGroup]:
    """Reorder (never add) the Master Resume skills by JD relevance."""
    jd_rank = _jd_skill_rank(jd)
    jd_lower = set(jd_rank)
    groups: List[tuple] = []
    for order, (key, label) in enumerate(SKILL_CATEGORIES.items()):
        skills = resume.skills.get(key)
        if not skills:
            continue
        ordered = [s for _, s in sorted(
            enumerate(skills), key=lambda p: _skill_sort_key(p[1], p[0], jd_rank, jd_lower))]
        relevant = sum(1 for s in skills if (normalize_skill(s) or s).lower() in jd_lower)
        groups.append((-relevant, order, SkillGroup(category=label, skills=ordered)))
    groups.sort(key=lambda g: (g[0], g[1]))
    return [g[2] for g in groups]


def _order_by_jd(items: List[str], jd_rank: Dict[str, int]) -> List[str]:
    return [s for _, s in sorted(
        enumerate(items),
        key=lambda p: (0, jd_rank[(normalize_skill(p[1]) or p[1]).lower()], p[0])
        if (normalize_skill(p[1]) or p[1]).lower() in jd_rank else (1, 0, p[0]))]


def rank_bullets(bullets: List[str], jd: JobDescriptionAnalysis) -> List[str]:
    """Stable-sort bullets by JD skill and keyword overlap (text unchanged)."""
    jd_skills = {s.lower() for s in jd.all_skills}
    keyword_tokens = {t for k in jd.keywords for t in tokenize(k)}

    def score(bullet: str) -> float:
        skills = {s.lower() for s in extract_skills(bullet)}
        tokens = set(tokenize(bullet))
        return 2.0 * len(skills & jd_skills) + 0.5 * len(tokens & keyword_tokens)

    return [b for _, b in sorted(enumerate(bullets), key=lambda p: (-score(p[1]), p[0]))]


def generate_summary(resume: MasterResume, jd: JobDescriptionAnalysis, match: MatchResult,
                     project_names: List[str]) -> str:
    """Factual summary built only from verified Master Resume data."""
    matched = match.matched_skills
    if not matched:
        return resume.summary.strip()

    title = next((e.title.strip() for e in resume.experience if e.title.strip()), "")
    top = matched[:5]
    lead = title if title else "Professional"
    sentences = [f"{lead} with hands-on experience in {join_human(top)}."]

    domains = []
    inventory = build_skill_inventory(resume)
    for skill in matched:
        category = skill_category(skill)
        if category in DOMAIN_CATEGORIES:
            label = SKILL_CATEGORIES[category]
            # A label like "AI / Machine Learning" itself implies skills; only use it if evidenced.
            implied = extract_skills(label)
            if label not in domains and all(s.lower() in inventory for s in implied):
                domains.append(label)
    if domains:
        sentences.append(f"Practical exposure spans {join_human(domains[:3])}.")
    if project_names:
        sentences.append(f"Key projects include {join_human(project_names[:3])}.")
    extra = matched[5:10]
    if extra:
        sentences.append(f"Also skilled in {join_human(extra)}.")
    return " ".join(sentences)


def generate_local_resume(resume: MasterResume, jd: JobDescriptionAnalysis, match: MatchResult,
                          ranking: ResumeRanking,
                          options: Optional[GenerationOptions] = None) -> TailoredResume:
    """Build a tailored resume using only Master Resume content."""
    options = options or GenerationOptions()
    defaults = default_selection(resume, ranking, options.max_projects)
    exp_ids = options.experience_ids if options.experience_ids is not None else defaults.experience_ids
    proj_ids = options.project_ids if options.project_ids is not None else defaults.project_ids
    cert_ids = (options.certification_ids if options.certification_ids is not None
                else defaults.certification_ids)
    jd_rank = _jd_skill_rank(jd)

    experience = []
    for exp in resume.experience:  # keep chronological order from the Master Resume
        if exp.id not in exp_ids:
            continue
        copy = exp.model_copy(deep=True)
        copy.bullets = rank_bullets(copy.bullets, jd)[:max(1, options.max_bullets_per_role)]
        copy.technologies = _order_by_jd(copy.technologies, jd_rank)
        experience.append(copy)

    project_order = {pid: i for i, pid in enumerate(item.ref_id for item in ranking.projects)}
    projects = []
    for project in sorted((p for p in resume.projects if p.id in proj_ids),
                          key=lambda p: project_order.get(p.id, 999)):
        copy = project.model_copy(deep=True)
        copy.responsibilities = rank_bullets(copy.responsibilities, jd)
        copy.technologies = _order_by_jd(copy.technologies, jd_rank)
        projects.append(copy)

    cert_order = {cid: i for i, cid in enumerate(item.ref_id for item in ranking.certifications)}
    certifications = [c.model_copy(deep=True) for c in sorted(
        (c for c in resume.certifications if c.id in cert_ids),
        key=lambda c: cert_order.get(c.id, 999))]

    return TailoredResume(
        personal=resume.personal.model_copy(deep=True),
        summary=generate_summary(resume, jd, match, [p.name for p in projects if p.name]),
        skills=reorder_skills(resume, jd),
        experience=experience,
        projects=projects,
        education=[e.model_copy(deep=True) for e in resume.education],
        certifications=certifications,
        achievements=[a.model_copy(deep=True) for a in resume.achievements]
        if options.include_achievements else [],
        target_job_title=jd.job_title,
        target_company=jd.company,
        generation_mode="local",
    )
