from __future__ import annotations

import json
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


BASE_DIR = Path(__file__).resolve().parents[1] / "data"
DOCS_PATH = BASE_DIR / "symcat_documents.json"


def _load_documents() -> list[str]:
    """Load the JSON document corpus used for lightweight retrieval."""
    with DOCS_PATH.open("r", encoding="utf-8") as handle:
        documents = json.load(handle)

    if not isinstance(documents, list):
        raise ValueError("symcat_documents.json must contain a list of documents.")

    return [str(document) for document in documents if str(document).strip()]


def retrieve_context(query: str, k: int = 3) -> list[str]:
    """
    Retrieve the most relevant documents for a user query using TF-IDF.

    This is a compatibility-friendly fallback approach that avoids FAISS and
    dense vector indexes, making retrieval easier to run in environments where
    native FAISS builds or precomputed indexes are not available.
    """
    documents = _load_documents()
    if not documents or not query.strip():
        return []

    # TF-IDF keeps the retrieval pipeline simple and portable while still
    # providing useful keyword-aware similarity ranking for symptom queries.
    vectorizer = TfidfVectorizer(stop_words="english")
    document_matrix = vectorizer.fit_transform(documents)
    query_vector = vectorizer.transform([query])

    similarities = cosine_similarity(query_vector, document_matrix).flatten()
    top_indices = similarities.argsort()[::-1][:k]

    return [documents[index] for index in top_indices if similarities[index] > 0]


if __name__ == "__main__":
    query = "sharp abdominal pain"
    results = retrieve_context(query)
    print(results)
