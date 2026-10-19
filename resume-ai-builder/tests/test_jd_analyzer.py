from services.jd_analyzer import analyze_jd, detect_job_title
from utils.skill_dictionary import extract_skills, normalize_skill


def test_skill_normalization():
    assert normalize_skill("python") == "Python"
    assert normalize_skill("PYTHON") == "Python"
    assert normalize_skill("ReactJS") == "React"
    assert normalize_skill("React.js") == "React"
    assert normalize_skill("RESTful API") == "REST API"
    assert normalize_skill("REST APIs") == "REST API"
    assert normalize_skill("ML") == "Machine Learning"
    assert normalize_skill("some random thing") is None


def test_extract_skills_conservative():
    skills = extract_skills("We use Java, JavaScript, C++ and HTML. Experience with ML is a plus.")
    assert {"Java", "JavaScript", "C++", "HTML", "Machine Learning"} <= set(skills)
    # "ML" inside "HTML" and "java" inside "javascript" must not create false positives
    assert extract_skills("HTML only") == ["HTML"]
    assert "Java" not in extract_skills("JavaScript developer")
    assert "Machine Learning" not in extract_skills("You will excel in a small team")


def test_skill_extraction(jd):
    assert {"Python", "FastAPI", "SQL", "Docker", "Kubernetes"} <= set(jd.required_skills)
    assert "AWS" in jd.preferred_skills
    assert "AWS" not in jd.required_skills


def test_job_title_extraction(jd):
    assert jd.job_title == "Python Developer"
    assert detect_job_title("Job Title: Senior Data Engineer\nWe build things") == \
        "Senior Data Engineer"
    assert detect_job_title("We are looking for a Machine Learning Engineer to join us") == \
        "Machine Learning Engineer"
    assert detect_job_title("anything", provided="AI Engineer") == "AI Engineer"


def test_keyword_extraction(jd):
    assert "Python" in jd.keywords
    assert len(jd.keywords) > 5


def test_requirements(jd):
    assert jd.min_years_experience == 2
    assert any("Bachelor" in e for e in jd.education_requirements)
    assert any("REST APIs" in r for r in jd.responsibilities)
    assert "Communication" in jd.soft_skills


def test_inline_preferred_cue():
    jd = analyze_jd("Requirements:\n- Python\n- Docker\n- Terraform is a plus")
    assert "Terraform" in jd.preferred_skills
    assert "Python" in jd.required_skills


def test_empty_jd():
    jd = analyze_jd("")
    assert jd.required_skills == [] and jd.keywords == []
