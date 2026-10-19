"""PDF / DOCX generation entry points (formatting only — no AI logic)."""

from __future__ import annotations

from models.resume_models import TailoredResume
from templates import TEMPLATES, ResumeTemplate
from utils.helpers import sanitize_filename
from utils.logger import get_logger

logger = get_logger("documents")

DEFAULT_TEMPLATE = "ats_professional"


class DocumentGenerationError(Exception):
    """Raised with a user-friendly message when export fails."""


def get_template(name: str) -> ResumeTemplate:
    return TEMPLATES.get(name) or TEMPLATES[DEFAULT_TEMPLATE]


def _render(resume: TailoredResume, template: str, fmt: str) -> bytes:
    try:
        return get_template(template).render(resume, fmt)
    except Exception as exc:
        logger.exception("%s generation failed (template=%s)", fmt.upper(), template)
        raise DocumentGenerationError(f"Could not generate the {fmt.upper()} file. "
                                      "Please try another template.") from exc


def generate_pdf(resume: TailoredResume, template: str = DEFAULT_TEMPLATE) -> bytes:
    return _render(resume, template, "pdf")


def generate_docx(resume: TailoredResume, template: str = DEFAULT_TEMPLATE) -> bytes:
    return _render(resume, template, "docx")


def build_filename(name: str, job_title: str, extension: str) -> str:
    """E.g. ``Bharath_Kumar_Python_Developer_Resume.pdf``."""
    parts = [p for p in (name, job_title, "Resume") if p and p.strip()]
    return f"{sanitize_filename(' '.join(parts))}.{extension.lstrip('.').lower()}"
