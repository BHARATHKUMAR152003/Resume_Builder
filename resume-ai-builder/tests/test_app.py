"""End-to-end UI flow using Streamlit's headless AppTest (no browser, no API key)."""

import pytest
from streamlit.testing.v1 import AppTest

from utils.sample_data import SAMPLE_JD


@pytest.fixture()
def app(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "session")  # never touch data/ during tests
    at = AppTest.from_file("../app.py", default_timeout=90)
    at.run()
    assert not at.exception
    return at


def _goto(at, page):
    at.selectbox(key="page").set_value(page).run()
    assert not at.exception, at.exception


def test_starts_in_local_mode(app):
    assert any("Local Mode" in s.value for s in app.success)
    assert not app.error


def test_full_local_workflow(app):
    _goto(app, "📄 Master Resume")
    app.button(key="btn_example_master").click().run()
    app.text_input(key="ed_p_name").set_value("Bharath Kumar").run()
    app.button(key="btn_save_master").click().run()
    assert app.session_state.master.personal.name == "Bharath Kumar"

    _goto(app, "💼 Job Description")
    app.button(key="btn_example_jd").click().run()
    app.button(key="btn_analyze").click().run()
    assert not app.exception
    assert app.session_state.page == "📊 JD Analysis"
    match = app.session_state.match
    assert "Kubernetes" in match.missing_skills and "Python" in match.matched_skills

    _goto(app, "✨ Generate Resume")
    assert app.button(key="btn_generate").disabled
    app.checkbox(key="gen_confirm").check().run()
    app.checkbox(key="sel_proj_proj_003").uncheck().run()
    app.button(key="btn_generate").click().run()
    assert not app.exception
    tailored = app.session_state.tailored
    assert tailored is not None and app.session_state.validation.is_valid
    assert "Railway Reservation System" not in [p.name for p in tailored.projects]
    assert "Kubernetes" not in tailored.model_dump_json()

    _goto(app, "👁 Preview")
    app.text_area(key="tr_summary").set_value("Expert in Kubernetes.").run()
    app.button(key="btn_apply_edits").click().run()
    assert not app.session_state.validation.is_valid

    _goto(app, "📥 Download")
    assert any("failed validation" in e.value for e in app.error)

    _goto(app, "👁 Preview")
    app.text_area(key="tr_summary").set_value("Software Engineer skilled in Python.").run()
    app.button(key="btn_apply_edits").click().run()
    assert app.session_state.validation.is_valid

    _goto(app, "📥 Download")
    assert not app.error
    assert len(app.get("download_button")) == 2

    # JD text and master resume survive navigation; master is untouched by generation
    assert app.session_state.jd_text == SAMPLE_JD
    assert app.session_state.master.summary.startswith("Software engineer with experience")


def test_empty_jd_shows_friendly_error(app):
    _goto(app, "💼 Job Description")
    app.button(key="btn_analyze").click().run()
    assert any("paste a job description" in e.value for e in app.error)


def test_settings_page(app):
    _goto(app, "⚙ Settings")
    app.radio(key="opt_mode").set_value("AI Enhanced Mode").run()
    assert not app.exception
    assert any("needs an API key" in w.value for w in app.warning)
