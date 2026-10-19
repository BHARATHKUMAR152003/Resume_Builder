"""Example data for demos and tests (fictional candidate)."""

from __future__ import annotations

from models.resume_models import (
    Achievement,
    Certification,
    Education,
    Experience,
    MasterResume,
    PersonalInfo,
    Project,
    SkillSet,
)

SAMPLE_JD = """Python Developer

We are hiring a Python Developer to build backend services for our analytics platform.

Responsibilities:
- Design and develop REST APIs using Python and FastAPI
- Write efficient SQL queries and maintain database schemas
- Containerize services with Docker and deploy them to production
- Collaborate with data scientists on machine learning features

Requirements:
- 2+ years of experience with Python
- Strong knowledge of FastAPI, SQL and Docker
- Experience with Kubernetes
- Bachelor's degree in Computer Science or a related field

Nice to have:
- AWS experience
- Good communication and problem-solving skills
"""


def sample_master_resume() -> MasterResume:
    return MasterResume(
        personal=PersonalInfo(
            name="Bharath Kumar", email="bharath.kumar@example.com", phone="+91 98765 43210",
            location="Bengaluru, India", linkedin="linkedin.com/in/bharath-kumar-example",
            github="github.com/bharath-example",
        ),
        summary="Software engineer with experience building Python backends, computer vision "
                "models and data-driven applications.",
        skills=SkillSet(
            programming_languages=["Python", "Java", "C++", "SQL"],
            ai_ml=["Machine Learning", "OpenCV", "YOLO", "Pandas"],
            deep_learning=["TensorFlow"],
            web_development=["React", "REST API"],
            frameworks=["FastAPI", "Flask"],
            databases=["MySQL", "PostgreSQL"],
            cloud=["AWS"],
            devops=["Docker"],
            tools=["Git", "Postman"],
        ),
        experience=[
            Experience(
                id="exp_001", company="Acme Analytics Pvt Ltd", title="Software Engineer",
                location="Bengaluru, India", start_date="Jul 2022", end_date="Present",
                bullets=[
                    "Built REST APIs with FastAPI and PostgreSQL serving 50,000 daily requests",
                    "Containerized microservices with Docker and deployed them on AWS EC2",
                    "Wrote SQL reports that reduced manual reporting effort by 30%",
                    "Mentored 2 junior developers on code reviews and testing",
                ],
                technologies=["Python", "FastAPI", "PostgreSQL", "Docker", "AWS"],
            ),
            Experience(
                id="exp_002", company="Bright Solutions", title="Java Developer Intern",
                location="Chennai, India", start_date="Jan 2022", end_date="Jun 2022",
                bullets=[
                    "Developed Spring Boot modules for an inventory system",
                    "Fixed 40 defects reported by the QA team",
                ],
                technologies=["Java", "Spring Boot", "MySQL"],
            ),
        ],
        projects=[
            Project(
                id="proj_001", name="RAG Application",
                description="Question answering over company documents using retrieval and a "
                            "FastAPI backend written in Python.",
                technologies=["Python", "FastAPI", "LangChain", "FAISS", "Docker"],
                responsibilities=["Implemented document chunking and retrieval in Python",
                                  "Exposed the pipeline through FastAPI endpoints"],
            ),
            Project(
                id="proj_002", name="Waste Detection",
                description="Real-time waste classification from camera images using Python.",
                technologies=["Python", "OpenCV", "YOLO", "TensorFlow", "Docker"],
                responsibilities=["Trained a YOLO model on 5,000 labelled images",
                                  "Packaged inference service with Docker"],
            ),
            Project(
                id="proj_003", name="Railway Reservation System",
                description="Desktop ticket booking application.",
                technologies=["Java", "MySQL"],
                responsibilities=["Designed the booking workflow and seat allocation logic"],
            ),
        ],
        education=[
            Education(id="edu_001", degree="B.Tech in Computer Science",
                      institution="Example Institute of Technology", location="Chennai",
                      start_date="2018", end_date="2022", gpa="8.4/10"),
        ],
        certifications=[
            Certification(id="cert_001", name="AWS Certified Cloud Practitioner",
                          issuer="Amazon Web Services", date="2023"),
            Certification(id="cert_002", name="Oracle Certified Java Programmer",
                          issuer="Oracle", date="2021"),
        ],
        achievements=[
            Achievement(id="ach_001", title="Hackathon Winner",
                        description="First place in a college hackathon for the Waste Detection project"),
        ],
    )
