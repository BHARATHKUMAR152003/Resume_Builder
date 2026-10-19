"""Template 2 — Modern: left-aligned header with a blue accent, still ATS-readable."""

from templates.base import ResumeTemplate, TemplateStyle


class ModernTemplate(ResumeTemplate):
    style = TemplateStyle(
        key="modern",
        label="Modern",
        pdf_font="Helvetica",
        docx_font="Calibri",
        accent="#1F4E79",
        text="#1A1A1A",
        muted="#555555",
        name_size=22,
        heading_size=12,
        center_header=False,
        heading_upper=False,
        heading_rule=True,
    )
