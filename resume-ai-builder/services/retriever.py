"""Local retrieval over Master Resume chunks (RAG-style, no vector DB needed).

``Retriever`` is an interface: ``LocalTfidfRetriever`` is the default; an
embedding/FAISS/Chroma retriever can be added later by implementing the same
two methods and registering it in ``create_retriever``.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Dict, Iterable, List, Optional

from pydantic import BaseModel, Field
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from models.jd_models import JobDescriptionAnalysis, RankedItem, ResumeRanking
from models.resume_models import MasterResume
from utils.helpers import unique
from utils.logger import get_logger
from utils.skill_dictionary import SKILL_CATEGORIES, extract_skills, normalize_skill

logger = get_logger("retriever")

# Raw TF-IDF cosine between a short chunk and a long JD rarely exceeds ~0.3,
# so scores are scaled against this reference before being combined.
TEXT_SCORE_REFERENCE = 0.30
TEXT_WEIGHT = 0.5
SKILL_WEIGHT = 0.5


class Chunk(BaseModel):
    id: str
    type: str
    title: str
    content: str
    skills: List[str] = Field(default_factory=list)
    ref_id: str = ""


class RetrievalResult(BaseModel):
    chunk: Chunk
    score: float


def _skill_token(skill: str) -> str:
    return "skill" + re.sub(r"[^a-z0-9+#]", "", skill.lower())


def _canonical_skills(values: Iterable[str]) -> List[str]:
    return unique(normalize_skill(v) or v for v in values if v)


def chunk_resume(resume: MasterResume) -> List[Chunk]:
    """Convert the Master Resume into retrievable chunks with metadata."""
    chunks: List[Chunk] = []
    if resume.summary.strip():
        chunks.append(Chunk(id="summary_001", type="summary", title="Professional Summary",
                            content=resume.summary, skills=extract_skills(resume.summary)))
    for key, label in SKILL_CATEGORIES.items():
        skills = resume.skills.get(key)
        if skills:
            chunks.append(Chunk(id=f"skill_{key}", type="skill", title=label,
                                content=", ".join(skills), skills=_canonical_skills(skills)))
    for exp in resume.experience:
        chunks.append(Chunk(
            id=exp.id, ref_id=exp.id, type="experience", title=exp.display_title(),
            content=exp.text(),
            skills=_canonical_skills(exp.technologies + extract_skills(exp.text())),
        ))
    for project in resume.projects:
        chunks.append(Chunk(
            id=project.id, ref_id=project.id, type="project", title=project.display_title(),
            content=project.text(),
            skills=_canonical_skills(project.technologies + extract_skills(project.text())),
        ))
    for edu in resume.education:
        chunks.append(Chunk(id=edu.id, ref_id=edu.id, type="education", title=edu.display_title(),
                            content=edu.text(), skills=extract_skills(edu.text())))
    for cert in resume.certifications:
        chunks.append(Chunk(id=cert.id, ref_id=cert.id, type="certification",
                            title=cert.display_title(), content=cert.text(),
                            skills=extract_skills(cert.text())))
    for ach in resume.achievements:
        chunks.append(Chunk(id=ach.id, ref_id=ach.id, type="achievement",
                            title=ach.display_title(), content=ach.text(),
                            skills=extract_skills(ach.text())))
    return chunks


class Retriever(ABC):
    """Retrieval interface used by the rest of the application."""

    @abstractmethod
    def index(self, chunks: List[Chunk]) -> None:
        raise NotImplementedError

    @abstractmethod
    def search(self, query: str, top_k: int = 5,
               types: Optional[Iterable[str]] = None) -> List[RetrievalResult]:
        raise NotImplementedError


class LocalTfidfRetriever(Retriever):
    """TF-IDF + cosine similarity retriever (keyword-based, not semantic)."""

    def __init__(self) -> None:
        self._chunks: List[Chunk] = []
        self._vectorizer: Optional[TfidfVectorizer] = None
        self._matrix = None

    @staticmethod
    def _enrich(text: str, skills: Iterable[str]) -> str:
        # Canonical skill tokens let "ReactJS" and "React.js" match each other.
        tokens = " ".join(_skill_token(s) for s in skills)
        return f"{text}\n{tokens}"

    def index(self, chunks: List[Chunk]) -> None:
        self._chunks = list(chunks)
        self._vectorizer, self._matrix = None, None
        if not self._chunks:
            return
        documents = [self._enrich(c.content, c.skills) for c in self._chunks]
        vectorizer = TfidfVectorizer(
            stop_words="english", ngram_range=(1, 2), sublinear_tf=True,
            token_pattern=r"(?u)[a-zA-Z][a-zA-Z0-9_+#]*",
        )
        try:
            self._matrix = vectorizer.fit_transform(documents)
            self._vectorizer = vectorizer
        except ValueError:  # empty vocabulary
            logger.info("TF-IDF index is empty; retrieval disabled for this resume")

    def search(self, query: str, top_k: int = 5,
               types: Optional[Iterable[str]] = None) -> List[RetrievalResult]:
        if not query or not query.strip() or self._vectorizer is None or top_k <= 0:
            return []
        query_vector = self._vectorizer.transform([self._enrich(query, extract_skills(query))])
        scores = cosine_similarity(query_vector, self._matrix).ravel()
        allowed = set(types) if types else None
        results = [
            RetrievalResult(chunk=chunk, score=float(score))
            for chunk, score in zip(self._chunks, scores)
            if score > 0 and (allowed is None or chunk.type in allowed)
        ]
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]


def create_retriever(kind: str = "tfidf") -> Retriever:
    """Factory — future: ``"faiss"``, ``"chroma"``, ``"embedding"``."""
    if kind == "tfidf":
        return LocalTfidfRetriever()
    raise ValueError(f"Unknown retriever type: {kind}")


def build_query(jd: JobDescriptionAnalysis) -> str:
    return "\n".join([jd.job_title, jd.raw_text, " ".join(jd.all_skills), " ".join(jd.keywords)])


def rank_resume(resume: MasterResume, jd: JobDescriptionAnalysis,
                retriever: Optional[Retriever] = None) -> ResumeRanking:
    """Rank experience / projects / certifications / achievements for a JD.

    Score = 50% scaled TF-IDF similarity + 50% weighted JD-skill overlap.
    """
    retriever = retriever or create_retriever()
    chunks = chunk_resume(resume)
    retriever.index(chunks)
    text_scores: Dict[str, float] = {
        r.chunk.id: r.score for r in retriever.search(build_query(jd), top_k=max(len(chunks), 1))
    }
    required = {s.lower() for s in jd.required_skills}
    preferred = {s.lower() for s in jd.preferred_skills}
    total_weight = len(required) + 0.5 * len(preferred)
    # A chunk covering ~6 JD skills is considered fully skill-relevant.
    denominator = min(total_weight, 6.0) if total_weight else 0.0

    ranking = ResumeRanking()
    buckets = {"experience": ranking.experience, "project": ranking.projects,
               "certification": ranking.certifications, "achievement": ranking.achievements}
    for chunk in chunks:
        if chunk.type not in buckets:
            continue
        matched = [s for s in chunk.skills if s.lower() in required or s.lower() in preferred]
        weight = sum(1.0 if s.lower() in required else 0.5 for s in matched)
        skill_score = min(1.0, weight / denominator) if denominator else 0.0
        raw_text = text_scores.get(chunk.id, 0.0)
        text_score = min(1.0, raw_text / TEXT_SCORE_REFERENCE)
        score = TEXT_WEIGHT * text_score + SKILL_WEIGHT * skill_score
        buckets[chunk.type].append(RankedItem(
            ref_id=chunk.ref_id, item_type=chunk.type, title=chunk.title,
            score=round(score, 4), text_score=round(raw_text, 4), matched_skills=matched,
        ))
    for items in buckets.values():
        items.sort(key=lambda item: item.score, reverse=True)
    return ranking
