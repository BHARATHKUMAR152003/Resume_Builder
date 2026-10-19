from models.resume_models import MasterResume, SkillSet
from services.jd_analyzer import analyze_jd
from services.resume_matcher import build_skill_inventory, match_resume, match_skill


def _status(match, skill):
    return next(m.status for m in match.skill_matches if m.skill == skill)


def test_example_from_spec(match):
    for skill in ("Python", "FastAPI", "SQL", "Docker", "AWS"):
        assert _status(match, skill) == "MATCH"
    assert _status(match, "Kubernetes") == "NOT_FOUND"
    assert "Kubernetes" in match.missing_skills


def test_exact_and_alias_match():
    resume = MasterResume(skills=SkillSet(web_development=["ReactJS"], programming_languages=["Python"]))
    inventory = build_skill_inventory(resume)
    exact = match_skill("Python", inventory)
    alias = match_skill("React", inventory)
    assert exact.status == "MATCH" and exact.method == "exact"
    assert alias.status == "MATCH" and alias.method == "alias"


def test_partial_match_related():
    resume = MasterResume(skills=SkillSet(databases=["MySQL"]))
    result = match_skill("PostgreSQL", build_skill_inventory(resume))
    assert result.status == "PARTIAL" and result.method == "related"


def test_partial_match_fuzzy():
    resume = MasterResume(skills=SkillSet(tools=["Kubeflow Pipelines"]))
    result = match_skill("Kubeflow Pipeline", build_skill_inventory(resume))
    assert result.status == "PARTIAL" and result.method == "fuzzy"


def test_missing_skill():
    resume = MasterResume(skills=SkillSet(programming_languages=["Python"]))
    assert match_skill("Terraform", build_skill_inventory(resume)).status == "NOT_FOUND"


def test_alignment_scores(match):
    assert 0 < match.overall_alignment <= 100
    assert match.required_total >= 5
    assert match.required_matched >= 4
    assert 0 <= match.keyword_coverage <= 100


def test_empty_resume_alignment(jd):
    result = match_resume(jd, MasterResume())
    assert result.overall_alignment == 0
    assert all(m.status == "NOT_FOUND" for m in result.skill_matches)


def test_unrelated_resume_scores_lower(master, match):
    jd = analyze_jd("Registered Nurse\nRequirements:\n- Patient care\n- ICU experience\n- BLS")
    assert match_resume(jd, master).overall_alignment < match.overall_alignment
