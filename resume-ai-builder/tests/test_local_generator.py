from services.local_resume_generator import (
    GenerationOptions,
    default_selection,
    generate_local_resume,
    generate_summary,
    rank_bullets,
)
from services.resume_validator import validate_resume


def test_local_generation_is_factual(master, jd, match, ranking):
    tailored = generate_local_resume(master, jd, match, ranking)
    text = tailored.model_dump_json()
    assert "Kubernetes" not in text
    assert validate_resume(tailored, master).is_valid
    master_skills = {s.lower() for s in master.skills.all_skills()}
    assert {s.lower() for s in tailored.all_skills()} == master_skills


def test_skills_reordered_not_added(master, jd, match, ranking):
    tailored = generate_local_resume(master, jd, match, ranking)
    languages = next(g for g in tailored.skills if g.category == "Programming Languages")
    assert languages.skills[:2] == ["Python", "SQL"]
    assert sorted(languages.skills) == sorted(master.skills.programming_languages)


def test_project_selection(master, ranking):
    selection = default_selection(master, ranking)
    assert set(selection.project_ids) >= {"proj_001", "proj_002"}
    assert "proj_003" not in selection.project_ids


def test_experience_selection(master, jd, match, ranking):
    tailored = generate_local_resume(master, jd, match, ranking,
                                     GenerationOptions(experience_ids=["exp_001"]))
    assert [e.id for e in tailored.experience] == ["exp_001"]
    master_bullets = set(master.experience[0].bullets)
    assert set(tailored.experience[0].bullets) <= master_bullets


def test_local_summary(master, jd, match):
    summary = generate_summary(master, jd, match, ["RAG Application"])
    assert summary.startswith("Software Engineer with hands-on experience in")
    assert "Python" in summary and "RAG Application" in summary
    assert "Kubernetes" not in summary


def test_summary_falls_back_to_original(master, jd, match):
    match.skill_matches = []
    assert generate_summary(master, jd, match, []) == master.summary


def test_bullet_ranking_preserves_text(jd):
    bullets = ["Organised team events", "Built REST APIs with FastAPI and Docker"]
    assert rank_bullets(bullets, jd) == list(reversed(bullets))


def test_master_resume_unchanged(master, jd, match, ranking):
    before = master.model_dump_json()
    generate_local_resume(master, jd, match, ranking, GenerationOptions(max_bullets_per_role=1))
    assert master.model_dump_json() == before
