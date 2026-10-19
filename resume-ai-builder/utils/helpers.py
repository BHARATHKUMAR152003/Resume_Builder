"""General text helpers shared across services."""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable, List, Set, Tuple

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

BULLET_RE = re.compile(r"^\s*(?:[•●▪◦‣∙·►➢➤✓✔○■□❖♦→]\s*|[*\-–—]\s+|\(?\d{1,2}[.)]\s+)")

# Words that are too generic to be useful JD keywords.
GENERIC_WORDS: Set[str] = {
    "experience", "experienced", "team", "teams", "work", "working", "role", "roles",
    "ability", "able", "strong", "skills", "skill", "knowledge", "years", "year",
    "candidate", "candidates", "job", "company", "including", "include", "understanding",
    "good", "excellent", "great", "related", "etc", "using", "use", "used", "based",
    "new", "plus", "preferred", "required", "requirement", "requirements",
    "responsibilities", "responsibility", "qualifications", "qualification", "must",
    "will", "help", "across", "within", "well", "also", "like", "looking", "join",
    "opportunity", "opportunities", "environment", "ideal", "minimum", "proven", "track",
    "record", "hands", "familiarity", "familiar", "solid", "deep", "nice", "bonus",
    "want", "need", "needs", "make", "ensure", "day", "high", "quality", "level",
    "including", "per", "key", "best", "practices", "practice", "relevant", "least",
    "degree", "field", "equivalent", "position", "apply", "description", "responsible",
    "seeking", "hiring", "us", "you", "your", "our", "we", "they", "them",
}

STOPWORDS: Set[str] = set(ENGLISH_STOP_WORDS) | GENERIC_WORDS


def clean_text(text: str) -> str:
    """Normalise whitespace / unicode while keeping line structure."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u200b", "").replace("\ufeff", "").replace("\t", " ")
    lines = [re.sub(r"[ \u00a0]{2,}", " ", line).strip() for line in text.split("\n")]
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def strip_bullet(line: str) -> Tuple[bool, str]:
    """Return ``(is_bullet, text_without_bullet)``."""
    match = BULLET_RE.match(line)
    if match:
        return True, line[match.end():].strip()
    return False, line.strip()


def unique(items: Iterable[str]) -> List[str]:
    """De-duplicate case-insensitively while preserving order."""
    seen: Set[str] = set()
    result: List[str] = []
    for item in items:
        if item is None:
            continue
        value = str(item).strip()
        key = value.lower()
        if value and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def split_items(text: str) -> List[str]:
    """Split comma / semicolon / pipe / newline separated lists."""
    if not text:
        return []
    parts = re.split(r"[\n,;|]", text)
    return unique(strip_bullet(p)[1].strip().rstrip(".").strip() for p in parts)


def split_lines(text: str) -> List[str]:
    """Split text into non-empty lines with bullets removed."""
    if not text:
        return []
    return [strip_bullet(line)[1] for line in text.splitlines() if strip_bullet(line)[1]]


def tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z][a-z0-9+#]*(?:[.\-][a-z0-9+#]+)*", text.lower())


def extract_numbers(text: str) -> Set[str]:
    """Extract numeric tokens (used for unsupported-metric detection)."""
    numbers = re.findall(r"\d+(?:[.,]\d+)*", text or "")
    return {n.replace(",", "").rstrip(".") for n in numbers}


def join_human(items: List[str]) -> str:
    items = [i for i in items if i]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


def sanitize_filename(name: str, max_length: int = 120) -> str:
    """Make a safe, portable filename component."""
    name = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    name = re.sub(r"[^A-Za-z0-9._ -]", "", name).strip().replace(" ", "_")
    name = re.sub(r"_+", "_", name).strip("._-")
    return name[:max_length] or "Resume"


def mask_secret(secret: str) -> str:
    if not secret:
        return ""
    return "••••••••" + secret[-4:] if len(secret) > 8 else "••••••••"


def contains_phrase(text_lower: str, phrase: str) -> bool:
    """Case-insensitive whole-phrase check (``text_lower`` must be lower-cased)."""
    phrase = phrase.lower().strip()
    if not phrase:
        return False
    pattern = r"(?<![a-z0-9+#])" + re.escape(phrase) + r"(?![a-z0-9+#])"
    return re.search(pattern, text_lower) is not None
