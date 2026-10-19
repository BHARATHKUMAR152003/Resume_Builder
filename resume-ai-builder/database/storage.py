"""Master Resume persistence. Swap ``JsonMasterResumeStore`` for a
Supabase/PostgreSQL implementation later by implementing ``MasterResumeStore``.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from models.resume_models import MasterResume
from utils.config import get_setting
from utils.file_utils import DATA_DIR, ensure_data_dir
from utils.logger import get_logger

logger = get_logger("storage")


class MasterResumeStore(ABC):
    persistent: bool = True

    @abstractmethod
    def load(self) -> Optional[MasterResume]:
        raise NotImplementedError

    @abstractmethod
    def save(self, resume: MasterResume) -> None:
        raise NotImplementedError

    @abstractmethod
    def delete(self) -> None:
        raise NotImplementedError


class JsonMasterResumeStore(MasterResumeStore):
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else DATA_DIR / "master_resume.json"

    def load(self) -> Optional[MasterResume]:
        if not self.path.is_file():
            return None
        try:
            return MasterResume.model_validate(json.loads(self.path.read_text(encoding="utf-8")))
        except (OSError, ValueError, ValidationError):
            logger.warning("Saved master resume could not be loaded")
            return None

    def save(self, resume: MasterResume) -> None:
        ensure_data_dir()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(resume.model_dump_json(indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    def delete(self) -> None:
        if self.path.is_file():
            self.path.unlink()


class SessionOnlyStore(MasterResumeStore):
    """No server-side persistence (recommended for public multi-user deployments)."""

    persistent = False

    def load(self) -> Optional[MasterResume]:
        return None

    def save(self, resume: MasterResume) -> None:
        return None

    def delete(self) -> None:
        return None


def get_master_resume_store() -> MasterResumeStore:
    backend = get_setting("STORAGE_BACKEND", "json").lower()
    if backend == "session":
        return SessionOnlyStore()
    return JsonMasterResumeStore()
