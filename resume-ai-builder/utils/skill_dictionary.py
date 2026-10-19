"""Central skill dictionary, aliases, categories and normalisation helpers.

To add a skill, add an entry to the relevant category in ``SKILLS_BY_CATEGORY``:
``"Canonical Name": ["lowercase alias", "another alias"]``.
Aliases are matched case-insensitively with word boundaries. Very short or
ambiguous aliases (e.g. "ML", "AI", "C", "R") belong in ``CASE_SENSITIVE_ALIASES``.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Dict, List, Optional, Set, Tuple

SKILL_CATEGORIES: Dict[str, str] = {
    "programming_languages": "Programming Languages",
    "ai_ml": "AI / Machine Learning",
    "deep_learning": "Deep Learning",
    "nlp": "NLP",
    "web_development": "Web Development",
    "frameworks": "Frameworks",
    "databases": "Databases",
    "cloud": "Cloud",
    "devops": "DevOps",
    "tools": "Tools",
    "other": "Other",
}

SKILLS_BY_CATEGORY: Dict[str, Dict[str, List[str]]] = {
    "programming_languages": {
        "Python": ["python", "python3"],
        "Java": ["java", "core java"],
        "JavaScript": ["javascript", "es6"],
        "TypeScript": ["typescript"],
        "C++": ["c++", "cpp"],
        "C#": ["c#", "csharp"],
        "C": [],
        "Go": ["golang"],
        "Rust": ["rust"],
        "Kotlin": ["kotlin"],
        "Swift": ["swift"],
        "PHP": ["php"],
        "Ruby": ["ruby"],
        "Scala": ["scala"],
        "R": [],
        "MATLAB": ["matlab"],
        "SQL": ["sql", "t-sql", "pl/sql", "plsql"],
        "Bash": ["bash", "shell scripting", "shell script"],
        "PowerShell": ["powershell"],
        "HTML": ["html", "html5"],
        "CSS": ["css", "css3"],
    },
    "ai_ml": {
        "Machine Learning": ["machine learning"],
        "Artificial Intelligence": ["artificial intelligence"],
        "Data Science": ["data science"],
        "Scikit-learn": ["scikit-learn", "sklearn", "scikit learn"],
        "Pandas": ["pandas"],
        "NumPy": ["numpy"],
        "XGBoost": ["xgboost"],
        "LightGBM": ["lightgbm"],
        "Computer Vision": ["computer vision"],
        "OpenCV": ["opencv"],
        "YOLO": ["yolo", "yolov5", "yolov7", "yolov8"],
        "Predictive Modeling": ["predictive modeling", "predictive modelling"],
        "Statistics": ["statistics", "statistical analysis", "statistical modeling"],
        "Data Analysis": ["data analysis", "data analytics"],
        "Data Visualization": ["data visualization", "data visualisation"],
        "Matplotlib": ["matplotlib"],
        "Seaborn": ["seaborn"],
        "MLOps": ["mlops"],
        "MLflow": ["mlflow"],
        "Generative AI": ["generative ai", "genai", "gen ai"],
        "RAG": ["rag", "retrieval augmented generation", "retrieval-augmented generation"],
        "LLM": ["llm", "llms", "large language model", "large language models"],
        "Prompt Engineering": ["prompt engineering"],
        "LangChain": ["langchain"],
        "LlamaIndex": ["llamaindex", "llama index"],
        "FAISS": ["faiss"],
        "Vector Database": ["vector database", "vector databases", "vector db"],
        "Time Series Forecasting": ["time series", "time-series", "time series forecasting"],
    },
    "deep_learning": {
        "Deep Learning": ["deep learning"],
        "TensorFlow": ["tensorflow"],
        "PyTorch": ["pytorch"],
        "Keras": ["keras"],
        "CNN": ["cnn", "cnns", "convolutional neural network", "convolutional neural networks"],
        "RNN": ["rnn", "rnns", "recurrent neural network", "recurrent neural networks"],
        "LSTM": ["lstm"],
        "Neural Networks": ["neural network", "neural networks"],
        "Transformers": ["transformers", "transformer models"],
    },
    "nlp": {
        "NLP": ["nlp", "natural language processing"],
        "spaCy": ["spacy"],
        "NLTK": ["nltk"],
        "Hugging Face": ["hugging face", "huggingface"],
        "BERT": ["bert"],
        "Text Classification": ["text classification"],
        "Sentiment Analysis": ["sentiment analysis"],
        "Named Entity Recognition": ["named entity recognition"],
        "TF-IDF": ["tf-idf", "tfidf"],
    },
    "web_development": {
        "React": ["react", "react.js", "reactjs"],
        "Angular": ["angular", "angularjs"],
        "Vue.js": ["vue", "vue.js", "vuejs"],
        "Node.js": ["node.js", "nodejs", "node js"],
        "Next.js": ["next.js", "nextjs"],
        "REST API": [
            "rest api", "rest apis", "restful api", "restful apis", "restful",
            "restful services", "rest services", "restful web services",
        ],
        "GraphQL": ["graphql"],
        "Microservices": ["microservices", "microservice"],
        "Tailwind CSS": ["tailwind", "tailwind css", "tailwindcss"],
        "Bootstrap": ["bootstrap"],
        "Streamlit": ["streamlit"],
        "jQuery": ["jquery"],
    },
    "frameworks": {
        "Django": ["django"],
        "Flask": ["flask"],
        "FastAPI": ["fastapi", "fast api"],
        "Spring Boot": ["spring boot", "springboot"],
        "Spring": ["spring framework", "spring mvc"],
        "Hibernate": ["hibernate"],
        ".NET": [".net", "dotnet", "asp.net", ".net core"],
        "Express.js": ["express.js", "expressjs"],
        "Pydantic": ["pydantic"],
        "Celery": ["celery"],
        "JUnit": ["junit"],
        "Pytest": ["pytest"],
        "Selenium": ["selenium"],
    },
    "databases": {
        "MySQL": ["mysql"],
        "PostgreSQL": ["postgresql", "postgres"],
        "SQL Server": ["sql server", "mssql", "microsoft sql server"],
        "Oracle Database": ["oracle database", "oracle db", "oracle sql"],
        "SQLite": ["sqlite"],
        "MongoDB": ["mongodb", "mongo db"],
        "Redis": ["redis"],
        "Cassandra": ["cassandra"],
        "DynamoDB": ["dynamodb"],
        "Elasticsearch": ["elasticsearch", "elastic search"],
        "Snowflake": ["snowflake"],
        "BigQuery": ["bigquery"],
        "Supabase": ["supabase"],
        "Firebase": ["firebase"],
    },
    "cloud": {
        "AWS": ["aws", "amazon web services"],
        "Azure": ["azure", "microsoft azure"],
        "GCP": ["gcp", "google cloud", "google cloud platform"],
        "AWS Lambda": ["aws lambda"],
        "Amazon S3": ["amazon s3", "aws s3"],
        "Amazon EC2": ["ec2", "amazon ec2", "aws ec2"],
        "Heroku": ["heroku"],
    },
    "devops": {
        "Docker": ["docker"],
        "Kubernetes": ["kubernetes", "k8s"],
        "Jenkins": ["jenkins"],
        "Terraform": ["terraform"],
        "Ansible": ["ansible"],
        "CI/CD": [
            "ci/cd", "ci cd", "cicd", "continuous integration",
            "continuous deployment", "continuous delivery",
        ],
        "GitHub Actions": ["github actions"],
        "GitLab CI": ["gitlab ci", "gitlab ci/cd"],
        "Linux": ["linux", "unix"],
        "Nginx": ["nginx"],
    },
    "tools": {
        "Git": ["git", "github", "gitlab"],
        "Jira": ["jira"],
        "Postman": ["postman"],
        "VS Code": ["vs code", "visual studio code", "vscode"],
        "Jupyter": ["jupyter", "jupyter notebook", "jupyter notebooks"],
        "Power BI": ["power bi", "powerbi"],
        "Tableau": ["tableau"],
        "Excel": ["ms excel", "microsoft excel", "advanced excel"],
        "Apache Airflow": ["airflow", "apache airflow"],
        "Apache Spark": ["spark", "apache spark", "pyspark"],
        "Hadoop": ["hadoop"],
        "Kafka": ["kafka", "apache kafka"],
        "Figma": ["figma"],
    },
    "other": {
        "Agile": ["agile"],
        "Scrum": ["scrum"],
        "OOP": [
            "oop", "oops", "object oriented programming", "object-oriented programming",
            "object-oriented design",
        ],
        "Data Structures": ["data structures"],
        "Algorithms": ["algorithms"],
        "Unit Testing": ["unit testing", "unit tests"],
        "System Design": ["system design"],
        "ETL": ["etl"],
        "Web Scraping": ["web scraping"],
    },
}

# Matched only when the exact casing appears, to avoid false positives.
CASE_SENSITIVE_ALIASES: Dict[str, List[str]] = {
    "Machine Learning": ["ML"],
    "Artificial Intelligence": ["AI"],
    "C": ["C"],
    "R": ["R"],
    "Excel": ["Excel"],
}

# Groups of interchangeable / closely related skills. A JD skill that is missing
# but has a sibling in the resume is reported as PARTIAL MATCH.
SKILL_FAMILIES: List[Set[str]] = [
    {"SQL", "MySQL", "PostgreSQL", "SQL Server", "Oracle Database", "SQLite"},
    {"MongoDB", "DynamoDB", "Cassandra"},
    {"AWS", "Azure", "GCP"},
    {"AWS", "AWS Lambda", "Amazon S3", "Amazon EC2"},
    {"TensorFlow", "PyTorch", "Keras"},
    {"Django", "Flask", "FastAPI"},
    {"React", "Angular", "Vue.js", "Next.js"},
    {"Jenkins", "GitHub Actions", "GitLab CI", "CI/CD"},
    {"Terraform", "Ansible"},
    {"Power BI", "Tableau"},
    {"JavaScript", "TypeScript"},
    {"Machine Learning", "Deep Learning", "Data Science", "Artificial Intelligence"},
    {"NLP", "spaCy", "NLTK", "Hugging Face", "BERT", "Transformers"},
    {"LLM", "Generative AI", "RAG", "LangChain", "LlamaIndex", "Prompt Engineering"},
    {"Spring Boot", "Spring"},
    {"Matplotlib", "Seaborn", "Data Visualization"},
    {"Computer Vision", "OpenCV", "YOLO"},
    {"FAISS", "Vector Database"},
]

SOFT_SKILLS: Dict[str, List[str]] = {
    "Communication": ["communication skills", "communication", "communicate"],
    "Teamwork": ["teamwork", "team player", "collaboration", "collaborate", "collaborative"],
    "Problem Solving": ["problem solving", "problem-solving"],
    "Leadership": ["leadership", "mentor", "mentoring"],
    "Analytical Thinking": ["analytical"],
    "Time Management": ["time management"],
    "Adaptability": ["adaptability", "adaptable", "fast-paced"],
    "Attention to Detail": ["attention to detail", "detail-oriented", "detail oriented"],
    "Critical Thinking": ["critical thinking"],
    "Ownership": ["ownership", "self-starter", "self starter"],
    "Stakeholder Management": ["stakeholder management", "stakeholders"],
}

_BOUNDARY_BEFORE = r"(?<![A-Za-z0-9_+#])"
_BOUNDARY_AFTER = r"(?![A-Za-z0-9_+#])"
_SINGLE_LETTER_AFTER = r"(?![A-Za-z0-9_+#&'\-])"


def _alias_regex(alias: str, case_sensitive: bool) -> re.Pattern[str]:
    escaped = re.escape(alias).replace(r"\ ", r"\s+")
    after = _SINGLE_LETTER_AFTER if len(alias) == 1 else _BOUNDARY_AFTER
    flags = 0 if case_sensitive else re.IGNORECASE
    return re.compile(_BOUNDARY_BEFORE + escaped + after, flags)


@lru_cache(maxsize=1)
def _skill_to_category() -> Dict[str, str]:
    return {
        skill: category
        for category, skills in SKILLS_BY_CATEGORY.items()
        for skill in skills
    }


@lru_cache(maxsize=1)
def get_skill_dictionary() -> Dict[str, List[str]]:
    """Return ``{canonical: [aliases...]}`` for every known skill."""
    merged: Dict[str, List[str]] = {}
    for skills in SKILLS_BY_CATEGORY.values():
        for canonical, aliases in skills.items():
            merged[canonical] = list(aliases)
    return merged


SKILL_DICTIONARY = get_skill_dictionary()


@lru_cache(maxsize=1)
def _compiled_patterns() -> List[Tuple[str, re.Pattern[str]]]:
    entries: List[Tuple[str, str, bool]] = []
    for canonical, aliases in get_skill_dictionary().items():
        for alias in aliases:
            entries.append((canonical, alias, False))
    for canonical, aliases in CASE_SENSITIVE_ALIASES.items():
        for alias in aliases:
            entries.append((canonical, alias, True))
    # Longest aliases first so multi-word skills win over sub-strings.
    entries.sort(key=lambda e: len(e[1]), reverse=True)
    return [(canonical, _alias_regex(alias, cs)) for canonical, alias, cs in entries]


@lru_cache(maxsize=1)
def _lookup_table() -> Dict[str, str]:
    table: Dict[str, str] = {}
    for canonical, aliases in get_skill_dictionary().items():
        table[_norm_key(canonical)] = canonical
        for alias in aliases:
            table[_norm_key(alias)] = canonical
    for canonical, aliases in CASE_SENSITIVE_ALIASES.items():
        for alias in aliases:
            table.setdefault(_norm_key(alias), canonical)
    return table


def _norm_key(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def normalize_skill(name: str) -> Optional[str]:
    """Map a skill string to its canonical name, or ``None`` if unknown.

    Only exact alias matches are accepted (conservative, no guessing).
    """
    if not name or not name.strip():
        return None
    key = _norm_key(name).strip(" .,;:")
    table = _lookup_table()
    if key in table:
        return table[key]
    if key.endswith("s") and key[:-1] in table:
        return table[key[:-1]]
    return None


def extract_skills(text: str) -> List[str]:
    """Return canonical skills mentioned in ``text`` ordered by first appearance."""
    if not text:
        return []
    positions: Dict[str, int] = {}
    for canonical, pattern in _compiled_patterns():
        match = pattern.search(text)
        if match and (canonical not in positions or match.start() < positions[canonical]):
            positions[canonical] = match.start()
    return [skill for skill, _ in sorted(positions.items(), key=lambda kv: kv[1])]


def skill_category(canonical: str) -> str:
    """Return the category key for a canonical skill (``"other"`` if unknown)."""
    return _skill_to_category().get(canonical, "other")


def get_aliases(canonical: str) -> List[str]:
    aliases = list(get_skill_dictionary().get(canonical, []))
    aliases.extend(a.lower() for a in CASE_SENSITIVE_ALIASES.get(canonical, []))
    return aliases


def related_skills(canonical: str) -> Set[str]:
    related: Set[str] = set()
    for family in SKILL_FAMILIES:
        if canonical in family:
            related |= family
    related.discard(canonical)
    return related


def extract_soft_skills(text: str) -> List[str]:
    found: Dict[str, int] = {}
    lowered = text.lower()
    for name, aliases in SOFT_SKILLS.items():
        for alias in aliases:
            match = re.search(_BOUNDARY_BEFORE + re.escape(alias) + _BOUNDARY_AFTER, lowered)
            if match and (name not in found or match.start() < found[name]):
                found[name] = match.start()
    return [name for name, _ in sorted(found.items(), key=lambda kv: kv[1])]
