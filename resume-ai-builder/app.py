"""ResumeAI — Streamlit entry point.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import html
import re
from datetime import datetime
from typing import Any, Dict, List, Tuple

import streamlit as st
from pydantic import SecretStr, ValidationError

from database.db import HistoryDB, get_history_db
from database.storage import MasterResumeStore, get_master_resume_store
from models.resume_models import (
    Achievement,
    Certification,
    Education,
    Experience,
    MasterResume,
    Project,
    TailoredResume,
)
from services.ai_service import (
    PROVIDERS,
    AIConfig,
    AIServiceError,
    create_provider,
    load_ai_config,
    validate_base_url,
)
from services.document_generator import (
    DEFAULT_TEMPLATE,
    DocumentGenerationError,
    build_filename,
    generate_docx,
    generate_pdf,
)
from services.jd_analyzer import analyze_jd
from services.llm_resume_generator import enhance_resume
from services.local_resume_generator import (
    GenerationOptions,
    default_selection,
    generate_local_resume,
)
from services.resume_matcher import match_resume
from services.resume_parser import ParseError, parse_resume_file
from services.resume_validator import validate_resume
from services.retriever import rank_resume
from templates import TEMPLATES
from templates.base import date_range
from utils.file_utils import MAX_UPLOAD_BYTES, MAX_UPLOAD_MB, FileValidationError
from utils.helpers import mask_secret, split_items, split_lines
from utils.logger import get_logger
from utils.sample_data import SAMPLE_JD, sample_master_resume
from utils.skill_dictionary import SKILL_CATEGORIES

logger = get_logger("app")

st.set_page_config(page_title="ResumeAI", page_icon="📄", layout="centered",
                   initial_sidebar_state="collapsed")

PAGES = ["🏠 Dashboard", "📄 Master Resume", "💼 Job Description", "📊 JD Analysis",
         "✨ Generate Resume", "👁 Preview", "📥 Download", "⚙ Settings"]
P_DASH, P_MASTER, P_JD, P_ANALYSIS, P_GENERATE, P_PREVIEW, P_DOWNLOAD, P_SETTINGS = PAGES

# Widget keys with these prefixes survive page switches (see persist_widget_state).
PERSIST_PREFIXES = ("ed_", "jd_", "sel_", "gen_", "tr_", "opt_")
MAX_JD_CHARS = 30_000
MODE_LOCAL, MODE_AI = "Local Mode", "AI Enhanced Mode"

TEMPLATE_DESCRIPTIONS = {
    "ats_professional": "Classic one-column layout, black text, ruled headings. Safest for ATS.",
    "modern": "Clean left-aligned layout with a subtle blue accent. ATS-readable.",
    "minimal": "Serif type, no lines, generous whitespace.",
}

MOBILE_CSS = """
<style>
.block-container {padding-top: 1.5rem; padding-bottom: 4rem; max-width: 760px;}
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
    width: 100%; min-height: 3rem; font-size: 1rem; border-radius: 10px;
}
textarea, input {font-size: 16px !important;}
h1 {margin-bottom: 0 !important;}
.rai-chip {display: inline-block; padding: 2px 10px; margin: 2px 3px; border-radius: 12px;
           font-size: 0.85rem; background: #eef2ff; color: #1e3a8a;}
.rai-chip.miss {background: #fef2f2; color: #991b1b;}
@media (max-width: 640px) {
    .block-container {padding-left: 0.8rem; padding-right: 0.8rem;}
    [data-testid="stMetricValue"] {font-size: 1.4rem;}
}
</style>
"""

PERSONAL_FIELDS = [("name", "Full Name"), ("email", "Email"), ("phone", "Phone"),
                   ("location", "Location"), ("linkedin", "LinkedIn"), ("github", "GitHub"),
                   ("portfolio", "Portfolio")]

# section -> (title, singular, model, [(field, label, kind)])
LIST_SECTIONS: Dict[str, Tuple[str, str, Any, List[Tuple[str, str, str]]]] = {
    "experience": ("💼 Professional Experience", "experience", Experience, [
        ("title", "Job Title", "text"), ("company", "Company", "text"),
        ("location", "Location", "text"), ("start_date", "Start Date", "text"),
        ("end_date", "End Date", "text"), ("description", "Description", "area"),
        ("bullets", "Bullet Points (one per line)", "lines"),
        ("technologies", "Technologies (comma separated)", "csv")]),
    "projects": ("🚀 Projects", "project", Project, [
        ("name", "Project Name", "text"), ("description", "Description", "area"),
        ("technologies", "Technologies (comma separated)", "csv"),
        ("responsibilities", "Responsibilities (one per line)", "lines"),
        ("results", "Results", "area"), ("achievements", "Achievements (one per line)", "lines")]),
    "education": ("🎓 Education", "education", Education, [
        ("degree", "Degree", "text"), ("institution", "Institution", "text"),
        ("location", "Location", "text"), ("start_date", "Start Date", "text"),
        ("end_date", "End Date", "text"), ("gpa", "GPA / Percentage", "text")]),
    "certifications": ("📜 Certifications", "certification", Certification, [
        ("name", "Name", "text"), ("issuer", "Issuer", "text"), ("date", "Date", "text"),
        ("credential", "Credential URL / ID", "text")]),
    "achievements": ("🏆 Achievements", "achievement", Achievement, [
        ("title", "Title", "text"), ("description", "Description", "area")]),
}


# =========================================================================== infrastructure

@st.cache_resource
def _store() -> MasterResumeStore:
    return get_master_resume_store()


@st.cache_resource
def _history() -> HistoryDB:
    return get_history_db()


@st.cache_resource
def _log_startup() -> bool:
    logger.info("ResumeAI application started")
    return True


@st.cache_data(show_spinner="Rendering document…", max_entries=24)
def _render_document(payload: str, template: str, fmt: str) -> bytes:
    resume = TailoredResume.model_validate_json(payload)
    return generate_pdf(resume, template) if fmt == "pdf" else generate_docx(resume, template)


def ss() -> Any:
    return st.session_state


def init_state() -> None:
    state = ss()
    if state.get("_initialized"):
        return
    master = _store().load() or MasterResume()
    state.master = master
    state.editor = master.model_copy(deep=True)
    state.ai_config = load_ai_config()
    state.opt_mode = MODE_AI if state.ai_config.is_configured else MODE_LOCAL
    state.analysis = state.match = state.ranking = state.jd_id = None
    state.tailored = state.validation = None
    state.gen_notes = []
    state.flash = []
    for key in ("jd_title", "jd_company", "jd_text"):
        state.setdefault(key, "")
    state.setdefault("page", P_DASH)
    state._initialized = True


def persist_widget_state() -> None:
    """Streamlit drops state of widgets that are not rendered; re-assigning keeps it."""
    state = ss()
    for key in list(state.keys()):
        if isinstance(key, str) and key.startswith(PERSIST_PREFIXES):
            state[key] = state[key]


def flash(kind: str, message: str) -> None:
    ss().flash.append((kind, message))


def show_flash() -> None:
    for kind, message in ss().flash:
        getattr(st, kind)(message)
    ss().flash = []


def go(page: str) -> None:
    ss().page = page


def nav_button(label: str, page: str, key: str, primary: bool = False) -> None:
    st.button(label, key=key, on_click=go, args=(page,), type="primary" if primary else "secondary")


def clear_keys(*prefixes: str) -> None:
    for key in list(ss().keys()):
        if isinstance(key, str) and key.startswith(prefixes):
            del ss()[key]


def ai_active() -> bool:
    return ss().get("opt_mode") == MODE_AI and ss().ai_config.is_configured


_MD_SPECIAL = re.compile(r"([\\`*_\[\]<>#$~|])")


def md(text: str) -> str:
    """Escape user text for Streamlit markdown."""
    escaped = _MD_SPECIAL.sub(r"\\\1", text or "")
    return re.sub(r"^(\s*)(\d+)\.", r"\1\2\\.", escaped)


def chips(items: List[str], missing: bool = False) -> None:
    if not items:
        st.caption("None found.")
        return
    css = "rai-chip miss" if missing else "rai-chip"
    st.markdown("".join(f'<span class="{css}">{html.escape(i)}</span>' for i in items),
                unsafe_allow_html=True)


def render_mode_status() -> None:
    if ai_active():
        provider = PROVIDERS[ss().ai_config.provider]["label"]
        st.success(f"🟢 **AI Enhanced Mode** — {provider}. All output is validated against "
                   "your Master Resume.")
    else:
        st.success("🟢 **Local Mode**\n\nNo external AI API is configured. ResumeAI is using "
                   "local matching and retrieval.")
        if ss().get("opt_mode") == MODE_AI:
            st.caption("AI Enhanced Mode is selected but no API key is configured, so Local "
                       "Mode is used.")


def reset_generation() -> None:
    state = ss()
    state.tailored = state.validation = None
    state.gen_notes = []
    clear_keys("sel_", "tr_")


def refresh_analysis() -> None:
    """Re-run matching after the Master Resume changes."""
    state = ss()
    if state.analysis is None:
        return
    state.ranking = rank_resume(state.master, state.analysis)
    state.match = match_resume(state.analysis, state.master, state.ranking)
    reset_generation()


# =========================================================================== dashboard

def page_dashboard() -> None:
    state = ss()
    st.header("🏠 Dashboard")
    col1, col2 = st.columns(2)
    col1.metric("Master Resume", "✓ Loaded" if not state.master.is_empty() else "Not set")
    col2.metric("Current Mode", "🟢 AI" if ai_active() else "🟢 Local")
    render_mode_status()

    if state.analysis is not None and state.match is not None:
        st.subheader("Latest Job")
        title = state.analysis.job_title or "Untitled role"
        st.markdown(f"**{md(title)}**" + (f" · {md(state.analysis.company)}"
                                          if state.analysis.company else ""))
        c1, c2, c3 = st.columns(3)
        c1.metric("Resume-JD Alignment", f"{state.match.overall_alignment:.0f}%")
        c2.metric("Matched Skills", len(state.match.matched_skills))
        c3.metric("Missing Skills", len(state.match.missing_skills))

    st.subheader("Get started")
    if state.master.is_empty():
        st.write("1. Create or upload your **Master Resume**.")
        nav_button("📄 Set up Master Resume", P_MASTER, "btn_dash_master", primary=True)
    else:
        st.write("Paste a job description to create a tailored resume.")
        nav_button("💼 Tailor for a new job", P_JD, "btn_dash_jd", primary=True)
        if state.tailored is not None:
            nav_button("📥 Download latest resume", P_DOWNLOAD, "btn_dash_dl")

    history = _history().list_generated(limit=8)
    if history:
        st.subheader("Recent Resumes")
        for row in history:
            try:
                when = datetime.fromisoformat(row["created_at"]).strftime("%d %b %Y")
            except (TypeError, ValueError):
                when = ""
            title = row.get("job_title") or "Untitled role"
            company = f" · {row['company']}" if row.get("company") else ""
            st.markdown(f"**{md(title)}**{md(company)}  \n"
                        f"<small>{html.escape(when)} · {row.get('alignment') or 0:.0f}% alignment · "
                        f"{html.escape(str(row.get('mode') or 'local'))}</small>",
                        unsafe_allow_html=True)


# =========================================================================== master resume

def load_into_editor(resume: MasterResume) -> None:
    ss().editor = resume
    clear_keys("ed_")


def _to_widget(value: Any, kind: str) -> str:
    if kind == "lines":
        return "\n".join(value or [])
    if kind == "csv":
        return ", ".join(value or [])
    return str(value or "")


def _from_widget(value: str, kind: str) -> Any:
    if kind == "lines":
        return split_lines(value)
    if kind == "csv":
        return split_items(value)
    return (value or "").strip()


def _widget(label: str, key: str, default: str, kind: str) -> None:
    if key not in ss():
        ss()[key] = default
    if kind in ("area", "lines"):
        st.text_area(label, key=key, height=150 if kind == "lines" else 100)
    elif kind == "csv":
        st.text_area(label, key=key, height=80)
    else:
        st.text_input(label, key=key)


def sync_editor() -> None:
    """Copy widget values into the editor model."""
    state = ss()
    editor: MasterResume = state.editor
    for field, _ in PERSONAL_FIELDS:
        if f"ed_p_{field}" in state:
            setattr(editor.personal, field, state[f"ed_p_{field}"].strip())
    if "ed_summary" in state:
        editor.summary = state["ed_summary"].strip()
    for category in SKILL_CATEGORIES:
        if f"ed_s_{category}" in state:
            setattr(editor.skills, category, split_items(state[f"ed_s_{category}"]))
    for section, (_, _, _, fields) in LIST_SECTIONS.items():
        for item in getattr(editor, section):
            for field, _, kind in fields:
                key = f"ed_{section}_{item.id}_{field}"
                if key in state:
                    setattr(item, field, _from_widget(state[key], kind))


def add_item(section: str) -> None:
    sync_editor()
    model = LIST_SECTIONS[section][2]
    item = model()
    getattr(ss().editor, section).append(item)
    ss()._open_item = item.id


def delete_item(section: str, item_id: str) -> None:
    sync_editor()
    items = getattr(ss().editor, section)
    items[:] = [i for i in items if i.id != item_id]


def move_item(section: str, item_id: str, delta: int) -> None:
    sync_editor()
    items = getattr(ss().editor, section)
    index = next(i for i, item in enumerate(items) if item.id == item_id)
    target = index + delta
    if 0 <= target < len(items):
        items[index], items[target] = items[target], items[index]
        ss()._open_item = item_id


def save_master() -> None:
    sync_editor()
    try:
        resume = MasterResume.model_validate(ss().editor.model_dump())
    except ValidationError:
        flash("error", "Some fields are invalid. Please review the Master Resume.")
        return
    if not resume.personal.name.strip():
        flash("warning", "Please enter your full name before saving.")
        return
    try:
        _store().save(resume)
    except OSError:
        logger.warning("Saving master resume to disk failed")
        flash("warning", "Could not write to disk — the resume is kept for this session only.")
    ss().master = resume.model_copy(deep=True)
    _history().save_master_resume(resume)
    refresh_analysis()
    flash("success", "✅ Master Resume saved.")


def handle_resume_upload(upload: Any) -> None:
    try:
        data = upload.getvalue()
        with st.spinner("Extracting resume content…"):
            result = parse_resume_file(data, upload.name)
    except (FileValidationError, ParseError) as exc:
        st.error(str(exc))
        return
    except Exception:
        logger.exception("Unexpected parsing error")
        st.error("Something went wrong while reading the file. Please try another format.")
        return
    load_into_editor(result.resume)
    found = ", ".join(result.sections_found) or "none"
    flash("success", f"Resume extracted (sections detected: {found}). Review the fields below, "
                     "correct anything that is wrong, then tap **Save Master Resume**.")
    for warning in result.warnings:
        flash("warning", warning)
    st.rerun()


def handle_json_import(upload: Any) -> None:
    data = upload.getvalue()
    if len(data) > MAX_UPLOAD_BYTES:
        st.error(f"File is too large. The maximum size is {MAX_UPLOAD_MB} MB.")
        return
    try:
        resume = MasterResume.model_validate_json(data)
    except (ValidationError, ValueError):
        st.error("This is not a valid ResumeAI Master Resume JSON file.")
        return
    load_into_editor(resume)
    flash("success", "Imported. Review the fields and tap **Save Master Resume**.")
    st.rerun()


def render_editor() -> None:
    state = ss()
    editor: MasterResume = state.editor
    with st.expander("👤 Personal Information", expanded=True):
        for field, label in PERSONAL_FIELDS:
            _widget(label, f"ed_p_{field}", getattr(editor.personal, field), "text")
    with st.expander("📝 Professional Summary"):
        _widget("Summary", "ed_summary", editor.summary, "area")
    with st.expander("🛠 Skills"):
        st.caption("Comma separated. Only skills listed here (or in your experience/projects) "
                   "can ever appear in a tailored resume.")
        for category, label in SKILL_CATEGORIES.items():
            _widget(label, f"ed_s_{category}", ", ".join(editor.skills.get(category)), "csv")

    for section, (title, singular, _, fields) in LIST_SECTIONS.items():
        items = getattr(editor, section)
        st.markdown(f"#### {title} ({len(items)})")
        for index, item in enumerate(items):
            with st.expander(f"{index + 1}. {item.display_title()}",
                             expanded=state.get("_open_item") == item.id):
                for field, label, kind in fields:
                    _widget(label, f"ed_{section}_{item.id}_{field}",
                            _to_widget(getattr(item, field), kind), kind)
                c1, c2, c3 = st.columns(3)
                c1.button("⬆ Move up", key=f"btn_up_{item.id}", on_click=move_item,
                          args=(section, item.id, -1), disabled=index == 0)
                c2.button("⬇ Move down", key=f"btn_down_{item.id}", on_click=move_item,
                          args=(section, item.id, 1), disabled=index == len(items) - 1)
                c3.button("🗑 Delete", key=f"btn_del_{item.id}", on_click=delete_item,
                          args=(section, item.id))
        st.button(f"➕ Add {singular}", key=f"btn_add_{section}", on_click=add_item,
                  args=(section,))
    sync_editor()


def page_master() -> None:
    state = ss()
    st.header("📄 Master Resume")
    st.info("Your Master Resume is the **single source of truth**. Add every genuine skill, "
            "role, project and certification here — tailored resumes only ever use this data.")

    with st.expander("⬆️ Upload an existing resume (PDF, DOCX, TXT)",
                     expanded=state.master.is_empty()):
        upload = st.file_uploader(f"Maximum {MAX_UPLOAD_MB} MB", type=["pdf", "docx", "txt"],
                                  key="upload_resume")
        st.caption("Uploading replaces the unsaved fields below with the extracted content.")
        if st.button("Extract resume content", key="btn_extract", disabled=upload is None,
                     type="primary"):
            handle_resume_upload(upload)

    with st.expander("More options"):
        if st.button("Load example data", key="btn_example_master"):
            load_into_editor(sample_master_resume())
            flash("info", "Example data loaded. Replace it with your own details before saving.")
            st.rerun()
        if not state.master.is_empty():
            st.download_button("Export Master Resume (JSON)", key="dl_master_json",
                               data=state.master.model_dump_json(indent=2),
                               file_name="master_resume.json", mime="application/json")
        json_upload = st.file_uploader("Import Master Resume (JSON)", type=["json"],
                                       key="upload_json")
        if st.button("Import JSON", key="btn_import_json", disabled=json_upload is None):
            handle_json_import(json_upload)
        if st.button("Discard unsaved changes", key="btn_revert"):
            load_into_editor(state.master.model_copy(deep=True))
            st.rerun()

    st.subheader("✏️ Edit Master Resume")
    render_editor()

    if state.editor.model_dump() != state.master.model_dump():
        st.warning("You have unsaved changes.")
    st.button("💾 Save Master Resume", type="primary", key="btn_save_master", on_click=save_master)
    if not _store().persistent:
        st.caption("This deployment does not store resumes on the server. Use **Export JSON** "
                   "to keep a copy and **Import JSON** next time.")
    if not state.master.is_empty():
        nav_button("💼 Continue to Job Description", P_JD, "btn_master_next")


# =========================================================================== job description

def run_analysis() -> None:
    state = ss()
    text = (state.get("jd_text") or "").strip()
    if not text:
        flash("error", "Please paste a job description first.")
        return
    if len(text) > MAX_JD_CHARS:
        text = text[:MAX_JD_CHARS]
        flash("warning", f"The JD was very long and was truncated to {MAX_JD_CHARS:,} characters.")
    try:
        analysis = analyze_jd(text, state.get("jd_title", ""), state.get("jd_company", ""))
        ranking = rank_resume(state.master, analysis)
        match = match_resume(analysis, state.master, ranking)
    except Exception:
        logger.exception("JD analysis failed")
        flash("error", "Something went wrong while analysing the job description. Please try again.")
        return
    state.analysis, state.ranking, state.match = analysis, ranking, match
    reset_generation()
    state.jd_id = _history().save_job_description(analysis.job_title, analysis.company, text,
                                                  match.overall_alignment)
    if state.master.is_empty():
        flash("warning", "Your Master Resume is empty, so nothing can be matched yet.")
    state.page = P_ANALYSIS


def clear_jd() -> None:
    state = ss()
    state.jd_title = state.jd_company = state.jd_text = ""
    state.analysis = state.match = state.ranking = None
    reset_generation()


def load_example_jd() -> None:
    ss().jd_title, ss().jd_company, ss().jd_text = "Python Developer", "Example Corp", SAMPLE_JD


def page_jd() -> None:
    st.header("💼 Job Description")
    st.text_input("Target Job Title", key="jd_title", placeholder="e.g. Python Developer")
    st.text_input("Target Company", key="jd_company", placeholder="Optional")
    st.text_area("Job Description", key="jd_text", height=380,
                 placeholder="Paste the complete job description here…")
    st.caption("The JD is treated as data only — instructions inside it are never followed.")
    st.button("🔍 Analyze JD", type="primary", key="btn_analyze", on_click=run_analysis)
    st.button("🧹 Clear", key="btn_clear_jd", on_click=clear_jd)
    st.button("Use example JD", key="btn_example_jd", on_click=load_example_jd)


# =========================================================================== analysis

def page_analysis() -> None:
    state = ss()
    st.header("📊 JD Analysis")
    if state.analysis is None or state.match is None:
        st.info("Analyze a job description first.")
        nav_button("💼 Go to Job Description", P_JD, "btn_analysis_jd", primary=True)
        return
    analysis, match, ranking = state.analysis, state.match, state.ranking

    st.markdown(f"**{md(analysis.job_title or 'Untitled role')}**"
                + (f" · {md(analysis.company)}" if analysis.company else ""))
    st.metric("Resume-JD Alignment", f"{match.overall_alignment:.0f}%")
    st.progress(min(1.0, match.overall_alignment / 100))
    st.caption("An estimate of how well your Master Resume covers this JD, using local keyword "
               "and skill matching. It is not a guaranteed ATS score.")
    c1, c2 = st.columns(2)
    c1.metric("Required Skills", f"{match.required_matched} / {match.required_total}",
              help=f"{match.required_partial} partial match(es) not counted")
    c2.metric("Preferred Skills", f"{match.preferred_matched} / {match.preferred_total}",
              help=f"{match.preferred_partial} partial match(es) not counted")
    c3, c4 = st.columns(2)
    c3.metric("Keyword Coverage", f"{match.keyword_coverage:.0f}%")
    c4.metric("Experience Relevance", f"{match.experience_relevance:.0f}%")
    st.caption(f"Project relevance: {match.project_relevance:.0f}% · "
               f"Text similarity: {match.text_similarity:.0f}%")

    st.subheader("Skill Match")
    groups = [("MATCH", "MATCH", "✓", "green"), ("PARTIAL", "PARTIAL MATCH", "◐", "orange"),
              ("NOT_FOUND", "NOT FOUND", "✗", "red")]
    for status, label, icon, color in groups:
        items = match.by_status(status)
        with st.expander(f"{icon} {label} ({len(items)})", expanded=bool(items)):
            if not items:
                st.caption("None.")
            for item in items:
                st.markdown(f":{color}[**{icon} {md(item.skill)}**] · {item.importance}")
                st.caption(item.evidence)
    if match.missing_skills:
        st.warning("These skills are **not** in your Master Resume and will **not** be added: "
                   + ", ".join(match.missing_skills))

    with st.expander("🔑 Important Keywords"):
        st.markdown("**Found in your resume**")
        chips(match.matched_keywords)
        st.markdown("**Not found**")
        chips(match.missing_keywords, missing=True)
    with st.expander("📋 Requirements"):
        st.markdown("**Required skills**")
        chips(analysis.required_skills)
        st.markdown("**Preferred skills**")
        chips(analysis.preferred_skills)
        if analysis.soft_skills:
            st.markdown("**Soft skills**")
            chips(analysis.soft_skills)
        for title, values in (("Experience", analysis.experience_requirements),
                              ("Education", analysis.education_requirements),
                              ("Certifications", analysis.certifications)):
            if values:
                st.markdown(f"**{title}**")
                st.markdown("\n".join(f"- {md(v)}" for v in values))
        if analysis.skills_by_category:
            st.markdown("**Skills by category**")
            for category, skills in analysis.skills_by_category.items():
                st.markdown(f"- {SKILL_CATEGORIES.get(category, category)}: {md(', '.join(skills))}")
    if analysis.responsibilities:
        with st.expander("🧾 Responsibilities"):
            st.markdown("\n".join(f"- {md(r)}" for r in analysis.responsibilities))

    st.subheader("Relevant content (Local Retrieval)")
    st.caption("Ranked by TF-IDF text similarity and JD skill overlap — keyword-based local "
               "retrieval, not semantic AI.")
    for label, items in (("Experience", ranking.experience), ("Projects", ranking.projects),
                         ("Certifications", ranking.certifications)):
        if items:
            st.markdown(f"**{label}**")
            for item in items:
                st.progress(min(1.0, item.score), text=f"{md(item.title)} — {item.score * 100:.0f}%")
    nav_button("✨ Continue to Generate Resume", P_GENERATE, "btn_analysis_next", primary=True)


# =========================================================================== generate

def _selection_checkbox(key: str, label: str, default: bool) -> None:
    if key not in ss():
        ss()[key] = default
    st.checkbox(label, key=key)


def run_generation() -> None:
    state = ss()
    master, analysis, match, ranking = state.master, state.analysis, state.match, state.ranking
    options = GenerationOptions(
        experience_ids=[e.id for e in master.experience if state.get(f"sel_exp_{e.id}")],
        project_ids=[p.id for p in master.projects if state.get(f"sel_proj_{p.id}")],
        certification_ids=[c.id for c in master.certifications if state.get(f"sel_cert_{c.id}")],
        max_bullets_per_role=int(state.get("gen_max_bullets", 6)),
        include_achievements=bool(state.get("gen_include_ach", True)),
    )
    try:
        tailored = generate_local_resume(master, analysis, match, ranking, options)
    except Exception:
        logger.exception("Local generation failed")
        flash("error", "Resume generation failed. Please review your Master Resume and try again.")
        return
    notes: List[str] = []
    if ai_active() and state.get("gen_use_ai", True):
        try:
            provider = create_provider(state.ai_config)
            if provider is not None:
                result = enhance_resume(provider, master, analysis, match, tailored)
                tailored, notes = result.resume, result.notes
        except AIServiceError as exc:
            notes.append(f"{exc} Using Local Mode result.")
        except Exception:
            logger.exception("AI enhancement failed")
            notes.append("AI enhancement failed. Using Local Mode result.")
    state.tailored = tailored
    state.validation = validate_resume(tailored, master)
    state.gen_notes = notes
    clear_keys("tr_")
    _history().save_generated_resume(tailored, match.overall_alignment,
                                     state.get("opt_template", DEFAULT_TEMPLATE), state.jd_id)


def render_generation_review() -> None:
    state = ss()
    report = state.validation
    valid = report is not None and report.is_valid
    lines = ["Relevant skills selected", "Relevant experience selected",
             "Relevant projects selected", "JD keywords incorporated where supported",
             "Unsupported claims checked", "ATS-friendly structure applied"]
    if valid:
        st.success("**Resume Generated**\n\n" + "\n".join(f"✓ {line}  " for line in lines))
    else:
        st.error("**Generation failed validation.** Unsupported claims were found — see the "
                 "Preview page to fix them. Download is blocked until resolved.")
    for note in state.get("gen_notes", []):
        st.info(note)


def page_generate() -> None:
    state = ss()
    st.header("✨ Generate Resume")
    if state.master.is_empty():
        st.warning("Your Master Resume is empty.")
        nav_button("📄 Set up Master Resume", P_MASTER, "btn_gen_master", primary=True)
        return
    if state.analysis is None:
        st.info("Analyze a job description first.")
        nav_button("💼 Go to Job Description", P_JD, "btn_gen_jd", primary=True)
        return
    master, ranking = state.master, state.ranking

    st.info("**Your Master Resume is the source of truth.**\n\nResumeAI will not add skills, "
            "experience, projects, certifications, or achievements that are not present in your "
            "Master Resume.")
    if "gen_confirm" not in state:
        state.gen_confirm = False
    st.checkbox("I confirm that my Master Resume contains accurate information.", key="gen_confirm")

    selection = default_selection(master, ranking)
    st.subheader("Select content")
    st.caption("Pre-selected by relevance. You have final control.")
    if master.experience:
        with st.expander(f"💼 Experience ({len(master.experience)})", expanded=True):
            for exp in master.experience:
                score = ranking.score_of(exp.id) * 100
                _selection_checkbox(f"sel_exp_{exp.id}", f"{exp.display_title()} · {score:.0f}%",
                                    exp.id in selection.experience_ids)
    if master.projects:
        order = {item.ref_id: i for i, item in enumerate(ranking.projects)}
        with st.expander(f"🚀 Projects ({len(master.projects)})", expanded=True):
            for project in sorted(master.projects, key=lambda p: order.get(p.id, 999)):
                score = ranking.score_of(project.id) * 100
                _selection_checkbox(f"sel_proj_{project.id}",
                                    f"{project.display_title()} · {score:.0f}%",
                                    project.id in selection.project_ids)
    if master.certifications:
        with st.expander(f"📜 Certifications ({len(master.certifications)})"):
            for cert in master.certifications:
                score = ranking.score_of(cert.id) * 100
                _selection_checkbox(f"sel_cert_{cert.id}", f"{cert.display_title()} · {score:.0f}%",
                                    cert.id in selection.certification_ids)
    with st.expander("⚙️ Options"):
        if "gen_max_bullets" not in state:
            state.gen_max_bullets = 6
        st.slider("Maximum bullets per role", 2, 10, key="gen_max_bullets")
        _selection_checkbox("gen_include_ach", "Include achievements", True)
        if ai_active():
            _selection_checkbox("gen_use_ai", "Use AI enhancement (validated)", True)
        else:
            st.caption("Local Mode: deterministic generation — original bullets are kept, "
                       "selected and reordered, never rewritten.")

    if st.button("✨ Generate Tailored Resume", type="primary", key="btn_generate",
                 disabled=not state.get("gen_confirm")):
        with st.spinner("Generating your tailored resume…"):
            run_generation()
        st.rerun()
    if not state.get("gen_confirm"):
        st.caption("Tick the confirmation box to enable generation.")

    if state.tailored is not None:
        render_generation_review()
        nav_button("👁 Preview & edit", P_PREVIEW, "btn_gen_preview", primary=True)
        nav_button("📥 Download", P_DOWNLOAD, "btn_gen_download")


# =========================================================================== preview

def render_preview(resume: TailoredResume) -> None:
    with st.container(border=True):
        st.markdown(f"### {md(resume.personal.name or 'Your Name')}")
        contacts = resume.personal.contact_items()
        if contacts:
            st.caption(" | ".join(md(c) for c in contacts))
        if resume.summary.strip():
            st.markdown("**PROFESSIONAL SUMMARY**")
            st.markdown(md(resume.summary))
        if any(g.skills for g in resume.skills):
            st.markdown("**TECHNICAL SKILLS**")
            st.markdown("\n".join(f"- **{md(g.category)}:** {md(', '.join(g.skills))}"
                                  for g in resume.skills if g.skills))
        if resume.experience:
            st.markdown("**EXPERIENCE**")
            for exp in resume.experience:
                meta = " | ".join(p for p in (exp.location, date_range(exp.start_date, exp.end_date)) if p)
                st.markdown(f"**{md(exp.display_title())}**" + (f"  \n_{md(meta)}_" if meta else ""))
                if exp.description:
                    st.markdown(md(exp.description))
                if exp.bullets:
                    st.markdown("\n".join(f"- {md(b)}" for b in exp.bullets))
                if exp.technologies:
                    st.caption("Technologies: " + md(", ".join(exp.technologies)))
        if resume.projects:
            st.markdown("**PROJECTS**")
            for project in resume.projects:
                st.markdown(f"**{md(project.name)}**")
                if project.technologies:
                    st.caption(md(", ".join(project.technologies)))
                if project.description:
                    st.markdown(md(project.description))
                items = project.responsibilities + project.achievements
                if project.results:
                    items.append(f"Result: {project.results}")
                if items:
                    st.markdown("\n".join(f"- {md(i)}" for i in items))
        if resume.education:
            st.markdown("**EDUCATION**")
            for edu in resume.education:
                meta = " | ".join(p for p in (edu.location, date_range(edu.start_date, edu.end_date),
                                              f"GPA/Score: {edu.gpa}" if edu.gpa else "") if p)
                st.markdown(f"**{md(edu.display_title())}**" + (f"  \n_{md(meta)}_" if meta else ""))
        if resume.certifications:
            st.markdown("**CERTIFICATIONS**")
            st.markdown("\n".join(
                f"- {md(c.display_title())}" + (f" ({md(c.date)})" if c.date else "")
                for c in resume.certifications))
        if resume.achievements:
            st.markdown("**ACHIEVEMENTS**")
            st.markdown("\n".join(f"- **{md(a.title)}**" + (f": {md(a.description)}"
                                                           if a.description else "")
                                  for a in resume.achievements))


def apply_tailored_edits() -> None:
    state = ss()
    resume: TailoredResume = state.tailored.model_copy(deep=True)
    if "tr_summary" in state:
        resume.summary = state["tr_summary"].strip()
    for index, group in enumerate(resume.skills):
        if f"tr_skills_{index}" in state:
            group.skills = split_items(state[f"tr_skills_{index}"])
    for exp in resume.experience:
        if f"tr_exp_{exp.id}_bullets" in state:
            exp.bullets = split_lines(state[f"tr_exp_{exp.id}_bullets"])
    for project in resume.projects:
        if f"tr_proj_{project.id}_description" in state:
            project.description = state[f"tr_proj_{project.id}_description"].strip()
        if f"tr_proj_{project.id}_resp" in state:
            project.responsibilities = split_lines(state[f"tr_proj_{project.id}_resp"])
    state.tailored = resume
    state.validation = validate_resume(resume, state.master)
    if state.validation.is_valid:
        flash("success", "Edits applied and validated.")
    else:
        flash("error", "Edits applied, but validation found unsupported claims (see below).")


def render_tailored_editor(resume: TailoredResume) -> None:
    st.caption("Edits apply only to this tailored resume — your Master Resume stays unchanged. "
               "Everything is re-validated against the Master Resume.")
    _widget("Professional Summary", "tr_summary", resume.summary, "area")
    for index, group in enumerate(resume.skills):
        _widget(f"Skills — {group.category}", f"tr_skills_{index}", ", ".join(group.skills), "csv")
    for exp in resume.experience:
        _widget(f"Bullets — {exp.display_title()}", f"tr_exp_{exp.id}_bullets",
                "\n".join(exp.bullets), "lines")
    for project in resume.projects:
        _widget(f"Description — {project.name}", f"tr_proj_{project.id}_description",
                project.description, "area")
        _widget(f"Responsibilities — {project.name}", f"tr_proj_{project.id}_resp",
                "\n".join(project.responsibilities), "lines")
    st.button("✅ Apply edits & re-validate", key="btn_apply_edits", on_click=apply_tailored_edits,
              type="primary")


def render_validation_details() -> None:
    report = ss().validation
    if report is None:
        return
    if report.is_valid:
        st.success("✓ Validation passed — every claim is supported by your Master Resume.")
    else:
        st.error("Generation failed validation. Fix these issues (edit below, or add the "
                 "information to your Master Resume if it is genuinely true):")
        st.markdown("\n".join(f"- **{md(i.category)}** — {md(i.item)}: {md(i.message)}"
                              for i in report.issues))
    if report.warnings:
        with st.expander(f"⚠️ Review suggestions ({len(report.warnings)})"):
            st.markdown("\n".join(f"- {md(w.item)} — {md(w.message)}" for w in report.warnings))


def page_preview() -> None:
    state = ss()
    st.header("👁 Preview")
    if state.tailored is None:
        st.info("Generate a tailored resume first.")
        nav_button("✨ Go to Generate Resume", P_GENERATE, "btn_prev_gen", primary=True)
        return
    render_validation_details()
    with st.expander("✏️ Edit tailored resume"):
        render_tailored_editor(state.tailored)
    render_preview(state.tailored)
    nav_button("📥 Continue to Download", P_DOWNLOAD, "btn_prev_next", primary=True)


# =========================================================================== download

def page_download() -> None:
    state = ss()
    st.header("📥 Download")
    if state.tailored is None:
        st.info("Generate a tailored resume first.")
        nav_button("✨ Go to Generate Resume", P_GENERATE, "btn_dl_gen", primary=True)
        return
    state.validation = validate_resume(state.tailored, state.master)
    render_generation_review()
    if not state.validation.is_valid:
        render_validation_details()
        nav_button("👁 Fix in Preview", P_PREVIEW, "btn_dl_fix", primary=True)
        return

    if state.get("opt_template") not in TEMPLATES:
        state.opt_template = DEFAULT_TEMPLATE
    st.radio("Template", list(TEMPLATES), key="opt_template",
             format_func=lambda key: TEMPLATES[key].label)
    template = state.opt_template
    st.caption(TEMPLATE_DESCRIPTIONS.get(template, ""))

    payload = state.tailored.model_dump_json()
    try:
        pdf = _render_document(payload, template, "pdf")
        docx = _render_document(payload, template, "docx")
    except DocumentGenerationError as exc:
        st.error(str(exc))
        return
    name = state.tailored.personal.name or "Resume"
    job = state.tailored.target_job_title or "Tailored"
    st.download_button("⬇️ Download PDF", data=pdf, file_name=build_filename(name, job, "pdf"),
                       mime="application/pdf", key="dl_pdf", type="primary")
    st.download_button(
        "⬇️ Download DOCX", data=docx, file_name=build_filename(name, job, "docx"),
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        key="dl_docx")
    st.caption("Your Master Resume is unchanged. You can tailor it for as many jobs as you like.")
    nav_button("💼 Tailor for another job", P_JD, "btn_dl_another")


# =========================================================================== settings

def save_ai_settings(provider: str, api_key: str, model: str, base_url: str) -> None:
    state = ss()
    if base_url and not validate_base_url(base_url):
        st.error("Base URL must start with https:// (or http://localhost for local models).")
        return
    if provider == "custom" and not base_url:
        st.error("A Base URL is required for a custom provider.")
        return
    current: AIConfig = state.ai_config
    key = api_key.strip() or (current.api_key.get_secret_value()
                              if current.provider == provider else "")
    state.ai_config = AIConfig(provider=provider, api_key=SecretStr(key), model=model.strip(),
                               base_url=base_url.strip())
    flash("success" if state.ai_config.is_configured else "warning",
          "AI settings saved." if state.ai_config.is_configured
          else "Settings saved, but an API key is still required for AI Enhanced Mode.")
    st.rerun()


def test_ai_connection() -> None:
    try:
        provider = create_provider(ss().ai_config)
        if provider is None:
            st.warning("AI is not configured.")
            return
        with st.spinner("Contacting provider…"):
            provider.complete('Reply with the JSON object {"ok": true}.', "ping", json_mode=False)
        st.success("Connection successful.")
    except AIServiceError as exc:
        st.error(str(exc))


def page_settings() -> None:
    state = ss()
    st.header("⚙ Settings")
    st.subheader("Application Mode")
    st.radio("Application Mode", [MODE_LOCAL, MODE_AI], key="opt_mode",
             label_visibility="collapsed")
    if state.opt_mode == MODE_LOCAL:
        st.success("No API key required. ResumeAI uses local NLP, TF-IDF retrieval and "
                   "rule-based generation.")
    else:
        config: AIConfig = state.ai_config
        if config.is_configured:
            st.success(f"🟢 AI Enhanced Mode ready — {PROVIDERS[config.provider]['label']} · "
                       f"model `{config.resolved_model}` · key {mask_secret(config.api_key.get_secret_value())}")
        else:
            st.warning("AI Enhanced Mode needs an API key. Until then ResumeAI keeps working "
                       "in Local Mode.")
        providers = list(PROVIDERS)
        with st.form("ai_settings"):
            provider = st.selectbox("Provider", providers, format_func=lambda p: PROVIDERS[p]["label"],
                                    index=providers.index(config.provider)
                                    if config.provider in providers else 0)
            api_key = st.text_input("API Key", type="password",
                                    placeholder="Leave blank to keep the current key")
            model = st.text_input("Model", value=config.model,
                                  placeholder="Default: " + (PROVIDERS[config.provider]["default_model"]
                                                             if config.provider in PROVIDERS else ""))
            base_url = st.text_input("Base URL (custom / local providers only)",
                                     value=config.base_url,
                                     placeholder="e.g. http://localhost:11434/v1 for Ollama")
            submitted = st.form_submit_button("Save AI settings", type="primary")
        if submitted:
            save_ai_settings(provider, api_key, model, base_url)
        st.caption("Keys entered here are held only in this session's server memory — never "
                   "written to disk, logs or history. For a permanent setup use `.env` locally or "
                   "Streamlit secrets in the cloud.")
        if config.is_configured:
            if st.button("Test connection", key="btn_test_ai"):
                test_ai_connection()
            if st.button("Remove API key", key="btn_remove_key"):
                state.ai_config = AIConfig()
                st.rerun()

    st.subheader("Data & Privacy")
    store = _store()
    st.write("Master Resume storage: " + ("local JSON file on the server" if store.persistent
                                           else "this browser session only"))
    st.write("Resume history: " + ("enabled (SQLite)" if _history().enabled else "disabled"))
    if _history().enabled and st.button("Clear resume history", key="btn_clear_history"):
        _history().clear()
        st.success("History cleared.")
    if store.persistent:
        if "opt_confirm_delete" not in state:
            state.opt_confirm_delete = False
        st.checkbox("I want to permanently delete my saved Master Resume", key="opt_confirm_delete")
        st.button("Delete saved Master Resume", key="btn_delete_master",
                  disabled=not state.opt_confirm_delete, on_click=delete_saved_master)


def delete_saved_master() -> None:
    state = ss()
    _store().delete()
    state.master = MasterResume()
    load_into_editor(MasterResume())
    refresh_analysis()
    state.opt_confirm_delete = False
    flash("success", "Saved Master Resume deleted.")


# =========================================================================== main

PAGE_RENDERERS = {
    P_DASH: page_dashboard, P_MASTER: page_master, P_JD: page_jd, P_ANALYSIS: page_analysis,
    P_GENERATE: page_generate, P_PREVIEW: page_preview, P_DOWNLOAD: page_download,
    P_SETTINGS: page_settings,
}


def main() -> None:
    _log_startup()
    init_state()
    persist_widget_state()
    st.markdown(MOBILE_CSS, unsafe_allow_html=True)
    st.title("ResumeAI")
    st.caption("Tailor your resume to every job — using only your real experience.")
    if ss().get("page") not in PAGES:
        ss().page = P_DASH
    st.selectbox("Navigate", PAGES, key="page", label_visibility="collapsed")
    show_flash()
    try:
        PAGE_RENDERERS[ss().page]()
    except Exception:
        logger.exception("Unhandled error on page %s", ss().page)
        st.error("Something went wrong on this page. Please try again or go back to the Dashboard.")


main()
