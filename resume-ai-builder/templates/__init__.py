"""Resume templates. Register new templates in ``TEMPLATES``."""

from typing import Dict

from templates.ats_professional import AtsProfessionalTemplate
from templates.base import ResumeTemplate
from templates.minimal import MinimalTemplate
from templates.modern import ModernTemplate

TEMPLATES: Dict[str, ResumeTemplate] = {
    t.key: t for t in (AtsProfessionalTemplate(), ModernTemplate(), MinimalTemplate())
}

__all__ = ["TEMPLATES", "ResumeTemplate"]
