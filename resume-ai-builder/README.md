# ResumeAI — Intelligent Job Description Based Resume Builder

> Tailor your resume to every job — using only your real experience.

ResumeAI is a mobile-friendly Streamlit app. You keep **one Master Resume** with all of your
genuine professional information, paste a Job Description (JD), and ResumeAI builds a
job-specific resume using **only** facts from your Master Resume. It never fabricates
skills, roles, projects, certifications or metrics.

**No API key is required.** All core features run locally. An LLM is an optional extra.

---

## Features

- **Master Resume**: upload a PDF / DOCX / TXT resume (parsed into structured fields) or create
  one by hand. Every section can be edited, and entries can be added, deleted and reordered.
  It is stored as JSON, and you can export or import it.
- **JD analysis (local)**: extracts the job title, required and preferred skills, skills by
  category, responsibilities, soft skills, experience, education and certification
  requirements, and important keywords.
- **Matching**: classifies each JD skill as **MATCH**, **PARTIAL MATCH** or **NOT FOUND**. It
  uses exact matching, alias matching, related-skill families, conservative fuzzy matching
  (RapidFuzz) and TF-IDF cosine similarity.
- **Resume-JD Alignment**: an overall alignment estimate plus required/preferred skill counts,
  keyword coverage, experience relevance and project relevance. This is *not* an ATS score.
- **Local retrieval (RAG-style)**: your Master Resume is split into chunks with metadata. JD-based
  TF-IDF retrieval then ranks your experience, projects and certifications.
- **Deterministic generation**: picks relevant content and reorders skills and bullets by JD
  relevance. It writes a factual summary from templates and never rewrites your bullets.
- **Validator**: blocks downloads if the tailored resume contains anything unsupported. That
  includes skills, technologies, companies, job titles, experience, projects, education,
  certifications, achievements and numbers/metrics.
- **User control**: you can select or deselect items, edit the tailored resume, and re-validate.
- **Export**: three templates (ATS Professional, Modern, Minimal) as A4 **PDF** (ReportLab) and
  **DOCX** (python-docx).
- **Optional AI Enhanced Mode**: any OpenAI-compatible provider (OpenRouter, OpenAI, or a
  local Ollama / LM Studio server). AI output is checked against a schema and validated, and
  ResumeAI falls back to Local Mode if anything fails.
- **Optional SQLite history** of analysed JDs and generated resumes.

## Architecture

```
app.py                      Streamlit UI (navigation, session state, pages)
models/                     Pydantic models (MasterResume, TailoredResume, JD analysis, matches)
services/
  resume_parser.py          PDF/DOCX/TXT text extraction + heuristic section parsing
  jd_analyzer.py            Rule-based JD analysis
  resume_matcher.py         Skill inventory, MATCH/PARTIAL/NOT FOUND, alignment scores
  retriever.py              Chunking, Retriever interface, LocalTfidfRetriever, ranking
  local_resume_generator.py Deterministic tailored resume generation
  resume_validator.py       Anti-fabrication validation
  ai_service.py             Optional OpenAI-compatible provider abstraction (stdlib only)
  llm_resume_generator.py   Optional LLM enhancement with prompt-injection protection
  document_generator.py     PDF/DOCX entry points + safe filenames
templates/                  ResumeTemplate interface + 3 templates (formatting only)
utils/                      Skill dictionary, helpers, config, logging, upload validation
database/                   JSON Master Resume store + optional SQLite history
tests/                      Unit tests + headless end-to-end UI test (no API key needed)
```

Data flow:

```
Master Resume ─┐
               ├─► JD analysis ─► Matching ─► Local retrieval ─► Generator ─► Validator ─► Preview ─► PDF/DOCX
Job Description┘                                                   ▲ (optional LLM, validated)
```

AI, retrieval, matching, generation and formatting are separate modules. Templates contain no
AI logic.

## Local Mode (default)

Local Mode is used whenever no API key is configured. It uses:

1. A **skill dictionary** (`utils/skill_dictionary.py`) with aliases and word-boundary regexes
   to extract and normalise skills. For example, `ReactJS` and `React.js` both become `React`,
   and `RESTful API` becomes `REST API`. Ambiguous short aliases (`ML`, `AI`, `C`, `R`) only
   match when the exact casing appears.
2. **JD section detection** ("Requirements", "Nice to have", "Responsibilities", …) plus inline
   cues ("… is a plus") to separate required from preferred skills.
3. **Matching**: exact → alias → related family (e.g. MySQL ↔ PostgreSQL = PARTIAL) →
   conservative fuzzy (ratio ≥ 88).
4. **TF-IDF + cosine similarity** for text similarity and retrieval. Each item's relevance is
   50% scaled TF-IDF similarity and 50% weighted JD-skill overlap.

This is *keyword-based local retrieval*, not semantic AI. To add semantic retrieval later,
implement the `Retriever` interface (e.g. with Sentence Transformers + FAISS) and register it
in `create_retriever()`. The UI does not need to change.

## AI Enhanced Mode (optional)

When enabled and configured, the LLM may only:

- rewrite the summary,
- rephrase existing bullets (keeping every fact), and
- reorder existing skills.

Safeguards:

- The system rules are kept separate from the data. Data is wrapped in `<MASTER_RESUME>`,
  `<JOB_DESCRIPTION>`, `<MATCHING_ANALYSIS>` and `<CURRENT_DRAFT>` tags, and any of those tags
  inside the data are stripped.
- The JD is explicitly marked as **untrusted data**, so instructions such as "ignore previous
  instructions…" are not followed.
- The output must be JSON matching a Pydantic schema. ResumeAI first tries safe parsing, then
  retries once, then falls back to Local Mode.
- Skills that are not in the Master Resume are dropped. The full validator then runs. If
  validation fails, the Local Mode resume is used.

## Installation (Windows)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

> **Tip:** If the project folder is synced by OneDrive, create the virtual environment outside
> it (e.g. `C:\Users\<you>\venvs\resumeai`). This avoids `WinError 32` file-lock errors.

Run:

```powershell
streamlit run app.py
```

Then open http://localhost:8501. To open it from your phone on the same Wi-Fi, use the
"Network URL" that Streamlit prints.

Run the tests (no API key needed):

```powershell
pip install -r requirements-dev.txt
pytest
```

## Configuration

Copy `.env.example` to `.env`. Every value is optional.

| Variable | Purpose |
|---|---|
| `AI_PROVIDER` | `local` (default), `openrouter`, `openai` or `custom` |
| `OPENROUTER_API_KEY` / `OPENAI_API_KEY` | Key for the chosen provider |
| `AI_API_KEY`, `AI_BASE_URL` | For `custom` OpenAI-compatible endpoints (HTTPS, or `http://localhost` for Ollama / LM Studio) |
| `AI_MODEL` | Model name (provider default if empty) |
| `STORAGE_BACKEND` | `json` (saves `data/master_resume.json`) or `session` (nothing stored on the server) |
| `ENABLE_HISTORY` | `true`/`false` — SQLite history in `data/resume_ai.db` |
| `LOG_LEVEL` | `INFO` by default. Logs never contain keys or resume content. |

You can also enter an API key at runtime on the **Settings** page. It is kept only in the
session's memory and is never written to disk or logs, and only its last 4 characters are
shown.

`.env`, `.streamlit/secrets.toml`, databases and everything in `data/` are git-ignored.

## Deployment — Streamlit Community Cloud

1. Push this folder to a GitHub repository. Personal data in `data/` is ignored automatically.
2. Open https://share.streamlit.io and sign in with GitHub.
3. Click **Create app** and select the repository and branch.
4. Set the main file path to `app.py`.
5. Click **Deploy**. No secrets are needed, and the app starts in Local Mode.
6. Optional: under **Settings → Secrets**, add the following, then reboot the app:
   ```toml
   STORAGE_BACKEND = "session"
   AI_PROVIDER = "openrouter"
   OPENROUTER_API_KEY = "sk-or-..."
   AI_MODEL = "openai/gpt-4o-mini"
   ```

> **Privacy on public deployments:** Community Cloud apps share one server file system, and it
> is wiped when the app restarts. For any app other people can open, set
> `STORAGE_BACKEND = "session"`. Then use **Export JSON / Import JSON** on the Master Resume page
> to keep your data on your phone. Also consider making the app private in Community Cloud.

Open the app URL in your phone's browser. You can add it to your home screen for an app-like
experience.

## Known limitations

- Resume parsing uses heuristics. Unusual layouts (multi-column PDFs, tables, graphics) may
  need manual correction in the editor. Scanned or image-only PDFs are not supported (no OCR).
- Skill detection relies on the dictionary. Skills it doesn't know are still kept from your
  Master Resume, but JDs are only analysed for known skills. Extend
  `SKILLS_BY_CATEGORY` as needed.
- TF-IDF matches keywords, not meaning. "Built web services" will not match "REST API" unless
  the term appears.
- The alignment score is a heuristic estimate, not a prediction of any real ATS.
- The JSON store is designed for one user. Multi-user use needs authentication and a
  per-user store.

## Recommended next improvements

- An `EmbeddingRetriever` (Sentence Transformers + FAISS) behind the existing `Retriever`
  interface.
- A Supabase/PostgreSQL `MasterResumeStore`, plus user login for multi-user deployments.
- A cover letter and interview-question generator that reuses the same validation pipeline.
- OCR for scanned PDFs, and LinkedIn profile import.
- Showing a resume history detail view, with re-download from the dashboard.
- Custom DOCX templates and PWA packaging.
