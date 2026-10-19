"""Template 3 — Minimal: serif type, no rules, generous whitespace."""

from templates.base import ResumeTemplate, TemplateStyle


class MinimalTemplate(ResumeTemplate):
    style = TemplateStyle(
        key="minimal",
        label="Minimal",
        pdf_font="Times",
        docx_font="Georgia",
        accent="#222222",
        muted="#555555",
        name_size=18,
        heading_size=11,
        body_size=10.5,
        center_header=False,
        heading_upper=True,
        heading_rule=False,
        margin_mm=20,
        section_space=10,
    )
