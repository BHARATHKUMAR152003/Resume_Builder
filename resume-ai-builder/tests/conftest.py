import pytest

from services.jd_analyzer import analyze_jd
from services.resume_matcher import match_resume
from services.retriever import rank_resume
from utils.sample_data import SAMPLE_JD, sample_master_resume


@pytest.fixture()
def master():
    return sample_master_resume()


@pytest.fixture()
def jd():
    return analyze_jd(SAMPLE_JD)


@pytest.fixture()
def ranking(master, jd):
    return rank_resume(master, jd)


@pytest.fixture()
def match(master, jd, ranking):
    return match_resume(jd, master, ranking)


@pytest.fixture(autouse=True)
def no_api_keys(monkeypatch):
    """Tests must never depend on (or leak) a real API key."""
    for name in ("OPENAI_API_KEY", "OPENROUTER_API_KEY", "AI_API_KEY", "AI_PROVIDER"):
        monkeypatch.delenv(name, raising=False)
