"""Validate a tailored resume against the Master Resume (anti-fabrication guard)."""

from __future__ import annotations

from typing import Iterable, List

from pydantic import BaseModel, Field
from rapidfuzz import fuzz

from models.resume_models import MasterResume, TailoredResume
from services.resume_matcher import build_skill_inventory
from utils.helpers import contains_phrase, extract_numbers
from utils.skill_dictionary import extract_skills, normalize_skill

NAME_MATCH_THRESHOLD = 90
BULLET_SIMILARITY_WARNING = 60


class ValidationIssue(BaseModel):
    category: str
    item: str
    message: str


class ValidationReport(BaseModel):
    is_valid: bool = True
    issues: List[ValidationIssue] = Field(default_factory=list)
    warnings: List[ValidationIssue] = Field(default_factory=list)

    def add_issue(self, category: str, item: str, message: str) -> None:
        self.issues.append(ValidationIssue(category=category, item=item, message=message))
        self.is_valid = False

    def add_warning(self, category: str, item: str, message: str) -> None:
        self.warnings.append(ValidationIssue(category=category, item=item, message=message))


def _known(value: str, candidates: Iterable[str]) -> bool:
    value = (value or "").strip().lower()
    if not value:
        return True
    return any(fuzz.ratio(value, c.strip().lower()) >= NAME_MATCH_THRESHOLD
               for c in candidates if c and c.strip())


def _skill_supported(skill: str, inventory: dict) -> bool:
    key = (normalize_skill(skill) or skill).strip().lower()
    return key in inventory or skill.strip().lower() in inventory


def validate_resume(tailored: TailoredResume, master: MasterResume) -> ValidationReport:
    """Detect any claim in ``tailored`` that is not supported by ``master``."""
    report = ValidationReport()
    inventory = build_skill_inventory(master)
    master_text = master.full_text()
    master_lower = master_text.lower()

    for field in ("name", "email", "phone"):
        value = getattr(tailored.personal, field).strip()
        if value and value != getattr(master.personal, field).strip():
            report.add_issue("Unsupported Personal Info", value,
                             f"{field.title()} differs from the Master Resume.")

    for skill in tailored.all_skills():
        if not _skill_supported(skill, inventory):
            report.add_issue("Unsupported Skill", skill, "Skill is not in the Master Resume.")

    for skill in extract_skills(tailored.narrative_text()):
        if skill.lower() not in inventory:
            report.add_issue("Unsupported Technology", skill,
                             "Technology is mentioned but not present in the Master Resume.")

    master_titles = [e.title for e in master.experience]
    master_companies = [e.company for e in master.experience]
    master_exp_text = [b for e in master.experience for b in e.bullets] + \
                      [e.description for e in master.experience if e.description]
    for exp in tailored.experience:
        if not _known(exp.company, master_companies):
            report.add_issue("Unsupported Company", exp.company, "Company is not in the Master Resume.")
        if not _known(exp.title, master_titles):
            report.add_issue("Unsupported Job Title", exp.title, "Job title is not in the Master Resume.")
        if not any(_known(exp.company, [m.company]) and _known(exp.title, [m.title])
                   for m in master.experience):
            report.add_issue("Unsupported Experience", exp.display_title(),
                             "This role does not exist in the Master Resume.")
        for tech in exp.technologies:
            if not _skill_supported(tech, inventory):
                report.add_issue("Unsupported Technology", tech,
                                 f"Listed under {exp.display_title()} but not in the Master Resume.")
        for bullet in exp.bullets:
            best = max((fuzz.token_set_ratio(bullet, m) for m in master_exp_text), default=0)
            if best < BULLET_SIMILARITY_WARNING:
                report.add_warning("Reworded Bullet", bullet[:80],
                                   "Bullet differs noticeably from the Master Resume — please review.")

    master_projects = [p.name for p in master.projects]
    for project in tailored.projects:
        if not _known(project.name, master_projects):
            report.add_issue("Unsupported Project", project.name, "Project is not in the Master Resume.")
        for tech in project.technologies:
            if not _skill_supported(tech, inventory):
                report.add_issue("Unsupported Technology", tech,
                                 f"Listed under {project.name} but not in the Master Resume.")

    for edu in tailored.education:
        if not any(_known(edu.degree, [m.degree]) and _known(edu.institution, [m.institution])
                   for m in master.education):
            report.add_issue("Unsupported Education", edu.display_title(),
                             "Education entry is not in the Master Resume.")
    for cert in tailored.certifications:
        if not _known(cert.name, [c.name for c in master.certifications]):
            report.add_issue("Unsupported Certification", cert.name,
                             "Certification is not in the Master Resume.")
    for ach in tailored.achievements:
        if not _known(ach.title, [a.title for a in master.achievements]):
            report.add_issue("Unsupported Achievement", ach.title,
                             "Achievement is not in the Master Resume.")

    master_numbers = extract_numbers(master_text)
    for number in sorted(extract_numbers(tailored.narrative_text()) - master_numbers):
        report.add_issue("Unsupported Metric", number,
                         "This number does not appear anywhere in the Master Resume.")

    target_title = tailored.target_job_title.strip()
    if target_title and contains_phrase(tailored.summary.lower(), target_title) \
            and not contains_phrase(master_lower, target_title):
        report.add_issue("Unsupported Job Title", target_title,
                         "The summary claims the target job title, which is not in your Master Resume.")
    return report
