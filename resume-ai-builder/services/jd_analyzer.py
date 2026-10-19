"""Rule-based Job Description analysis (no external API required)."""

from __future__ import annotations

import re
from collections import Counter
from typing import Dict, List, Optional

from models.jd_models import JobDescriptionAnalysis
from utils.helpers import STOPWORDS, clean_text, strip_bullet, tokenize, unique
from utils.skill_dictionary import (
    extract_skills,
    extract_soft_skills,
    get_aliases,
    skill_category,
)

JD_SECTION_ALIASES: Dict[str, List[str]] = {
    "required": [
        "requirements", "required", "required skills", "required qualifications", "must have",
        "must-have", "must haves", "qualifications", "minimum qualifications",
        "basic qualifications", "what you need", "what you'll need", "what we're looking for",
        "what we are looking for", "skills required", "key skills", "technical skills", "skills",
        "who you are", "you have", "your profile", "requirements and skills",
        "skills and qualifications", "eligibility", "mandatory skills", "about you",
        "desired profile", "candidate profile", "job requirements", "skills and experience",
    ],
    "preferred": [
        "preferred", "preferred skills", "preferred qualifications", "nice to have",
        "nice-to-have", "good to have", "good-to-have", "bonus", "bonus points", "pluses",
        "plus", "desirable", "desired skills", "additional skills", "it would be great if",
        "nice to haves", "bonus skills", "optional skills",
    ],
    "responsibilities": [
        "responsibilities", "key responsibilities", "job responsibilities",
        "roles and responsibilities", "what you'll do", "what you will do", "duties", "the role",
        "your role", "day to day", "about the role", "your responsibilities",
        "job description", "role and responsibilities", "what you will be doing",
    ],
    "other": [
        "about us", "about the company", "who we are", "benefits", "perks", "what we offer",
        "why join us", "compensation", "salary", "location", "company overview", "our culture",
        "equal opportunity", "how to apply",
    ],
}
_HEADING_LOOKUP = {alias: key for key, aliases in JD_SECTION_ALIASES.items() for alias in aliases}

PREFERRED_CUE_RE = re.compile(
    r"\b(preferred|nice[- ]to[- ]have|good[- ]to[- ]have|bonus|is a plus|are a plus|a plus"
    r"|desirable|advantageous|added advantage|optional|would be great|ideally)\b",
    re.IGNORECASE,
)
YEARS_RE = re.compile(
    r"\b(\d{1,2}(?:\.\d)?)\s*\+?\s*(?:(?:-|–|to)\s*(\d{1,2})\s*\+?\s*)?(?:years?|yrs?)\b",
    re.IGNORECASE,
)
EDUCATION_RE = re.compile(
    r"\b(bachelor'?s?|master'?s?|degree|b\.?\s?tech|m\.?\s?tech|b\.e\.?|m\.e\.?|ph\.?\s?d"
    r"|mca|bca|b\.?sc|m\.?sc|graduate|graduation|computer science|engineering)\b",
    re.IGNORECASE,
)
CERT_RE = re.compile(r"\b(certifi\w*|certified)\b", re.IGNORECASE)
TITLE_LINE_RE = re.compile(
    r"^\s*(?:job title|position|role|title|designation|job role|opening)\s*[:\-–]\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)
COMPANY_LINE_RE = re.compile(r"^\s*(?:company|organization|employer)\s*[:\-–]\s*(.+)$",
                             re.IGNORECASE | re.MULTILINE)
TITLE_WORDS_RE = re.compile(
    r"\b(engineer|developer|manager|analyst|intern|scientist|lead|consultant|architect|designer"
    r"|specialist|administrator|programmer|researcher|tester|devops|sre)\b",
    re.IGNORECASE,
)
HIRING_RE = re.compile(
    r"\b(?:hiring|looking for|seeking|searching for)\s+(?:an?\s+)?"
    r"(?:(?:experienced|talented|skilled|motivated|passionate|senior|junior|mid-level)\s+)*"
    r"((?:[A-Z][\w+#./-]*\s*){1,5})",
)
ACTION_VERBS = {
    "develop", "design", "build", "implement", "maintain", "collaborate", "work", "create",
    "lead", "manage", "write", "test", "deploy", "optimize", "optimise", "analyze", "analyse",
    "ensure", "participate", "support", "troubleshoot", "integrate", "own", "drive", "mentor",
    "architect", "automate", "monitor", "review", "document", "deliver", "contribute",
    "partner", "research", "translate", "improve", "debug", "conduct", "define", "perform",
}


def _normalize_heading(line: str) -> str:
    value = line.strip().strip("#*_=:-–—|•").strip().lower()
    value = value.replace("’", "'").replace("&", " and ")
    return re.sub(r"\s+", " ", value)


def _heading_and_rest(line: str) -> tuple[Optional[str], str]:
    """Detect ``Heading`` or ``Heading: inline content`` lines."""
    stripped = line.strip()
    if not stripped:
        return None, ""
    if len(stripped.split()) <= 7:
        key = _HEADING_LOOKUP.get(_normalize_heading(stripped))
        if key:
            return key, ""
    if ":" in stripped:
        prefix, rest = stripped.split(":", 1)
        key = _HEADING_LOOKUP.get(_normalize_heading(prefix))
        if key and len(prefix.split()) <= 5:
            return key, rest.strip()
    return None, stripped


def detect_job_title(text: str, provided: str = "") -> str:
    if provided.strip():
        return provided.strip()
    if m := TITLE_LINE_RE.search(text):
        return m.group(1).strip()[:80]
    for m in HIRING_RE.finditer(text):
        candidate = m.group(1).strip(" .,")
        if TITLE_WORDS_RE.search(candidate):
            return candidate[:80]
    for line in text.split("\n")[:5]:
        line = line.strip(" #*:")
        if line and len(line.split()) <= 8 and TITLE_WORDS_RE.search(line):
            return line[:80]
    return ""


def extract_keywords(text: str, skills: List[str], top_n: int = 15) -> List[str]:
    """Skills first, then the most frequent meaningful unigrams / bigrams."""
    covered = {s.lower() for s in skills}
    for skill in skills:
        covered.update(a.lower() for a in get_aliases(skill))
    counts: Counter[str] = Counter()
    for line in text.split("\n"):
        tokens = [t.strip(".-") for t in tokenize(line)]
        for i, token in enumerate(tokens):
            if token in STOPWORDS or len(token) < 3 or token.isdigit():
                continue
            counts[token] += 1
            if i + 1 < len(tokens) and token not in ACTION_VERBS:
                nxt = tokens[i + 1]
                if nxt not in STOPWORDS and len(nxt) >= 3:
                    counts[f"{token} {nxt}"] += 1.5
    terms: List[str] = []
    for term, count in counts.most_common():
        if len(terms) >= top_n:
            break
        if count < 2 and len(terms) >= 5:
            continue
        if term in covered or any(part in covered for part in term.split()):
            continue
        if any(term in existing or existing in term for existing in terms):
            continue
        terms.append(term)
    return unique(skills + terms)


def analyze_jd(text: str, job_title: str = "", company: str = "") -> JobDescriptionAnalysis:
    """Analyse a job description using local rules and the skill dictionary."""
    text = clean_text(text or "")
    analysis = JobDescriptionAnalysis(raw_text=text, company=company.strip())
    if not text:
        analysis.job_title = job_title.strip()
        return analysis

    analysis.job_title = detect_job_title(text, job_title)
    if not analysis.company and (m := COMPANY_LINE_RE.search(text)):
        analysis.company = m.group(1).strip()[:80]

    required: List[str] = []
    preferred: List[str] = []
    responsibilities: List[str] = []
    experience_reqs: List[str] = []
    education_reqs: List[str] = []
    certifications: List[str] = []
    section = "general"

    for raw in text.split("\n"):
        heading, content = _heading_and_rest(raw)
        if heading and not content:
            section = heading
            continue
        if heading == "other":
            continue  # e.g. "Location: Pune" — metadata, not requirements
        if heading:
            section = heading
        is_bullet, line = strip_bullet(content)
        if not line:
            continue

        skills = extract_skills(line)
        if section == "preferred" or PREFERRED_CUE_RE.search(line):
            preferred.extend(skills)
        elif section != "other":
            required.extend(skills)

        if section == "responsibilities":
            responsibilities.append(line)
        elif is_bullet and section == "general":
            first = line.split()[0].lower().rstrip("s,:") if line.split() else ""
            if first in ACTION_VERBS:
                responsibilities.append(line)
        if YEARS_RE.search(line) and ("experience" in line.lower()
                                      or section in {"required", "preferred"}):
            experience_reqs.append(line)
        if EDUCATION_RE.search(line) and re.search(r"degree|bachelor|master|graduat|b\.?\s?tech|"
                                                   r"m\.?\s?tech|ph\.?\s?d|b\.e|mca|bca",
                                                   line, re.IGNORECASE):
            education_reqs.append(line)
        if CERT_RE.search(line):
            certifications.append(line)

    analysis.required_skills = unique(required)
    required_lower = {s.lower() for s in analysis.required_skills}
    analysis.preferred_skills = [s for s in unique(preferred) if s.lower() not in required_lower]

    by_category: Dict[str, List[str]] = {}
    for skill in analysis.all_skills:
        by_category.setdefault(skill_category(skill), []).append(skill)
    analysis.skills_by_category = by_category

    analysis.responsibilities = unique(responsibilities)[:20]
    analysis.soft_skills = extract_soft_skills(text)
    analysis.experience_requirements = unique(experience_reqs)[:10]
    analysis.education_requirements = unique(education_reqs)[:10]
    analysis.certifications = unique(certifications)[:10]
    years = [float(m.group(1)) for line in experience_reqs for m in YEARS_RE.finditer(line)]
    analysis.min_years_experience = min(years) if years else None
    analysis.keywords = extract_keywords(text, analysis.all_skills)
    return analysis
