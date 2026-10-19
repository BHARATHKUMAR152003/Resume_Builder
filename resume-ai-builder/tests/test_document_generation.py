import io

import pymupdf
import pytest
from docx import Document

from models.resume_models import Experience, PersonalInfo, TailoredResume
from services.document_generator import build_filename, generate_docx, generate_pdf
from services.local_resume_generator import generate_local_resume
from templates import TEMPLATES


@pytest.fixture()
def tailored(master, jd, match, ranking):
    return generate_local_resume(master, jd, match, ranking)


@pytest.mark.parametrize("template", list(TEMPLATES))
def test_pdf_creation(tailored, template):
    data = generate_pdf(tailored, template)
    assert data.startswith(b"%PDF")
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        text = "\n".join(page.get_text() for page in doc)
        width = doc[0].rect.width
        pages = doc.page_count
    assert round(width) == 595  # A4
    assert pages <= 2  # nested KeepTogether once inflated this sample to 4 pages
    assert "Bharath Kumar" in text
    assert "RAG Application" in text
    assert "Kubernetes" not in text


@pytest.mark.parametrize("template", list(TEMPLATES))
def test_docx_creation(tailored, template):
    data = generate_docx(tailored, template)
    document = Document(io.BytesIO(data))
    text = "\n".join(p.text for p in document.paragraphs)
    assert "Bharath Kumar" in text and "PROFESSIONAL EXPERIENCE" in text.upper()
    assert abs(document.sections[0].page_width.mm - 210) < 1


def test_special_characters_and_long_content():
    resume = TailoredResume(
        personal=PersonalInfo(name="Zoë <O'Brien> & Co"),
        summary="Uses C++ & C# <daily>. " * 40,
        experience=[Experience(title="Engineer", company="A&B", bullets=["x" * 30 + " y" * 200] * 30)],
    )
    with pymupdf.open(stream=generate_pdf(resume), filetype="pdf") as doc:
        assert doc.page_count >= 2
    assert generate_docx(resume)


def test_filename():
    assert build_filename("Bharath Kumar", "Python Developer", "pdf") == \
        "Bharath_Kumar_Python_Developer_Resume.pdf"
    assert build_filename("../../etc/passwd", "AI/ML Engineer", "docx") == \
        "etcpasswd_AIML_Engineer_Resume.docx"
