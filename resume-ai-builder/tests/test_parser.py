import io

import pymupdf
import pytest
from docx import Document

from services.resume_parser import (
    ParseError,
    detect_heading,
    detect_sections,
    parse_resume_file,
    parse_resume_text,
)
from utils.file_utils import MAX_UPLOAD_BYTES, FileValidationError, validate_upload

RESUME_TEXT = """Bharath Kumar
Bengaluru, India | bharath.kumar@example.com | +91 98765 43210
linkedin.com/in/bharath-kumar-example | github.com/bharath-example

Professional Summary
Software engineer building Python backends and computer vision models.

Technical Skills
Programming Languages: Python, Java, SQL
AI/ML: TensorFlow, OpenCV, YOLO
Cloud: AWS, Azure
Tools: Git, Docker

Work Experience
Software Engineer | Acme Analytics Pvt Ltd | Jul 2022 - Present
- Built REST APIs with FastAPI and PostgreSQL serving 50,000 daily requests
- Containerized services with Docker and deployed them on AWS
Java Developer Intern | Bright Solutions | Jan 2022 - Jun 2022
- Developed Spring Boot modules for an inventory system

Projects
Waste Detection (Python, OpenCV, YOLO)
- Trained a YOLO model on 5,000 labelled images
RAG Application
- Built document retrieval with FAISS and FastAPI

Education
B.Tech in Computer Science, Example Institute of Technology, 2018 - 2022, CGPA: 8.4/10

Certifications
AWS Certified Cloud Practitioner - Amazon Web Services - 2023

Achievements
Hackathon Winner: First place in a college hackathon
"""


def _assert_parsed(result):
    resume = result.resume
    assert resume.personal.name == "Bharath Kumar"
    assert resume.personal.email == "bharath.kumar@example.com"
    assert "98765" in resume.personal.phone
    assert "linkedin.com/in/bharath-kumar-example" in resume.personal.linkedin
    assert "Python" in resume.skills.programming_languages
    assert "TensorFlow" in resume.skills.ai_ml
    assert len(resume.experience) == 2
    first = resume.experience[0]
    assert first.title == "Software Engineer"
    assert "Acme" in first.company
    assert first.start_date == "Jul 2022" and first.end_date == "Present"
    assert len(first.bullets) == 2
    assert "FastAPI" in first.technologies
    assert [p.name for p in resume.projects] == ["Waste Detection", "RAG Application"]
    assert "OpenCV" in resume.projects[0].technologies
    assert resume.education and "B.Tech" in resume.education[0].degree
    assert resume.education[0].gpa.startswith("8.4")
    assert resume.certifications[0].name == "AWS Certified Cloud Practitioner"
    assert resume.achievements[0].title == "Hackathon Winner"


def test_section_aliases():
    for heading in ("Experience", "WORK EXPERIENCE", "Professional Experience:", "Employment",
                    "Career History"):
        assert detect_heading(heading) == "experience"
    for heading in ("Skills", "Technical Skills", "Core Skills", "Technologies"):
        assert detect_heading(heading) == "skills"
    assert detect_heading("I have experience with many things in my career") is None


def test_detect_sections():
    sections = detect_sections(RESUME_TEXT)
    assert {"summary", "skills", "experience", "projects", "education"} <= set(sections)


def test_parse_txt():
    _assert_parsed(parse_resume_file(RESUME_TEXT.encode("utf-8"), "resume.txt"))


def test_parse_docx():
    document = Document()
    for line in RESUME_TEXT.split("\n"):
        document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)
    _assert_parsed(parse_resume_file(buffer.getvalue(), "resume.docx"))


def test_parse_pdf():
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((40, 40), RESUME_TEXT, fontsize=8)
    data = doc.tobytes()
    doc.close()
    _assert_parsed(parse_resume_file(data, "resume.pdf"))


def test_unsupported_file_type():
    with pytest.raises(FileValidationError):
        validate_upload("resume.exe", b"MZ...")


def test_file_too_large():
    with pytest.raises(FileValidationError):
        validate_upload("resume.txt", b"a" * (MAX_UPLOAD_BYTES + 1))


def test_invalid_pdf():
    with pytest.raises(FileValidationError):
        parse_resume_file(b"not a pdf at all", "resume.pdf")


def test_corrupted_pdf():
    with pytest.raises(ParseError):
        parse_resume_file(b"%PDF-1.4 garbage garbage", "resume.pdf")


def test_empty_resume():
    with pytest.raises(ParseError):
        parse_resume_text("   ")
