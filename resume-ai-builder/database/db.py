"""Optional SQLite history. Every method fails soft: the app works without it."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from models.resume_models import MasterResume, TailoredResume
from utils.config import get_bool_setting, get_setting
from utils.file_utils import DATA_DIR
from utils.logger import get_logger

logger = get_logger("db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS master_resumes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS job_descriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_title TEXT,
    company TEXT,
    jd_text TEXT,
    alignment REAL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS generated_resumes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_description_id INTEGER REFERENCES job_descriptions(id),
    job_title TEXT,
    company TEXT,
    alignment REAL,
    template TEXT,
    mode TEXT,
    resume TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class HistoryDB:
    def __init__(self, path: Path | None = None, enabled: bool = True) -> None:
        self.path = Path(path) if path else DATA_DIR / "resume_ai.db"
        self.enabled = enabled
        if self.enabled:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with closing(self._connect()) as conn, conn:
                    conn.executescript(SCHEMA)
            except sqlite3.Error:
                logger.warning("SQLite unavailable; history disabled")
                self.enabled = False

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _execute(self, sql: str, params: tuple = ()) -> Optional[int]:
        if not self.enabled:
            return None
        try:
            with closing(self._connect()) as conn, conn:
                return conn.execute(sql, params).lastrowid
        except sqlite3.Error:
            logger.warning("History write failed")
            return None

    def save_master_resume(self, resume: MasterResume) -> Optional[int]:
        return self._execute(
            "INSERT INTO master_resumes (name, data, created_at) VALUES (?, ?, ?)",
            (resume.personal.name, resume.model_dump_json(), _now()),
        )

    def save_job_description(self, job_title: str, company: str, jd_text: str,
                             alignment: float) -> Optional[int]:
        return self._execute(
            "INSERT INTO job_descriptions (job_title, company, jd_text, alignment, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (job_title, company, jd_text, alignment, _now()),
        )

    def save_generated_resume(self, resume: TailoredResume, alignment: float, template: str,
                              job_description_id: Optional[int] = None) -> Optional[int]:
        return self._execute(
            "INSERT INTO generated_resumes (job_description_id, job_title, company, alignment, "
            "template, mode, resume, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (job_description_id, resume.target_job_title, resume.target_company, alignment,
             template, resume.generation_mode, resume.model_dump_json(), _now()),
        )

    def list_generated(self, limit: int = 10) -> List[Dict[str, Any]]:
        if not self.enabled:
            return []
        try:
            with closing(self._connect()) as conn:
                rows = conn.execute(
                    "SELECT id, job_title, company, alignment, template, mode, created_at "
                    "FROM generated_resumes ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.Error:
            return []

    def get_generated(self, resume_id: int) -> Optional[TailoredResume]:
        if not self.enabled:
            return None
        try:
            with closing(self._connect()) as conn:
                row = conn.execute("SELECT resume FROM generated_resumes WHERE id = ?",
                                   (resume_id,)).fetchone()
            return TailoredResume.model_validate_json(row["resume"]) if row else None
        except (sqlite3.Error, ValueError):
            return None

    def clear(self) -> None:
        for table in ("generated_resumes", "job_descriptions", "master_resumes"):
            self._execute(f"DELETE FROM {table}")  # table names are constants


def get_history_db() -> HistoryDB:
    enabled = get_bool_setting("ENABLE_HISTORY", True) and \
        get_setting("STORAGE_BACKEND", "json").lower() != "session"
    return HistoryDB(enabled=enabled)
