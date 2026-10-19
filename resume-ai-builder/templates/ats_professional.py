"""Template 1 — ATS Professional: classic single-column, black text, ruled headings."""

from templates.base import ResumeTemplate, TemplateStyle


class AtsProfessionalTemplate(ResumeTemplate):
    style = TemplateStyle(
        key="ats_professional",
        label="ATS Professional",
        pdf_font="Helvetica",
        docx_font="Calibri",
        accent="#000000",
        center_header=True,
        heading_upper=True,
        heading_rule=True,
    )
