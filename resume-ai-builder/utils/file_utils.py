"""Upload validation and filesystem helpers."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

MAX_UPLOAD_MB = 10
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}


class FileValidationError(ValueError):
    """Raised with a user-friendly message when an upload is rejected."""


def get_extension(filename: str) -> str:
    return Path(filename or "").suffix.lower()


def validate_upload(filename: str, data: bytes) -> str:
    """Validate an uploaded resume file and return its extension."""
    ext = get_extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise FileValidationError("Unsupported file type. Please upload a PDF, DOCX or TXT file.")
    if not data:
        raise FileValidationError("The uploaded file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise FileValidationError(f"File is too large. The maximum size is {MAX_UPLOAD_MB} MB.")
    if ext == ".pdf" and not data[:1024].lstrip().startswith(b"%PDF"):
        raise FileValidationError("This file does not look like a valid PDF.")
    if ext == ".docx" and not data.startswith(b"PK"):
        raise FileValidationError("This file does not look like a valid DOCX document.")
    return ext


def ensure_data_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR
