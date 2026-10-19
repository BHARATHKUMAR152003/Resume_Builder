from models.resume_models import MasterResume
from services.retriever import LocalTfidfRetriever, Retriever, chunk_resume, create_retriever


def test_chunking(master):
    chunks = chunk_resume(master)
    types = {c.type for c in chunks}
    assert {"summary", "skill", "experience", "project", "education", "certification",
            "achievement"} <= types
    waste = next(c for c in chunks if c.title == "Waste Detection")
    assert {"Python", "OpenCV", "YOLO"} <= set(waste.skills)


def test_tfidf_search(master):
    retriever = create_retriever()
    assert isinstance(retriever, Retriever) and isinstance(retriever, LocalTfidfRetriever)
    retriever.index(chunk_resume(master))
    results = retriever.search("computer vision YOLO OpenCV object detection", top_k=3,
                               types=["project"])
    assert results and results[0].chunk.title == "Waste Detection"
    assert all(r.chunk.type == "project" for r in results)


def test_ranking_for_python_jd(ranking):
    titles = [p.title for p in ranking.projects]
    assert set(titles[:2]) == {"RAG Application", "Waste Detection"}
    assert titles[-1] == "Railway Reservation System"
    assert ranking.experience[0].title.startswith("Software Engineer")


def test_empty_query(master):
    retriever = LocalTfidfRetriever()
    retriever.index(chunk_resume(master))
    assert retriever.search("") == []
    assert retriever.search("   ") == []


def test_empty_index():
    retriever = LocalTfidfRetriever()
    retriever.index(chunk_resume(MasterResume()))
    assert retriever.search("python") == []
