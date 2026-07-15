from __future__ import annotations
import pickle
from pathlib import Path
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

BASE_DIR = Path(__file__).resolve().parents[1] / "data"
INDEX_PATH = BASE_DIR / "symcat_index.faiss"
DOCS_PATH = BASE_DIR / "symcat_docs.pkl"
MODEL_NAME = "all-MiniLM-L6-v2"

# Global variables to prevent reloading
_model = None
_index = None
_documents = None

def get_resources():
    """Load model, index, and docs into memory once."""
    global _model, _index, _documents
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    if _index is None:
        if INDEX_PATH.exists():
            _index = faiss.read_index(str(INDEX_PATH))
        else:
            print("Warning: INDEX_PATH not found.")
    if _documents is None:
        if DOCS_PATH.exists():
            with DOCS_PATH.open("rb") as handle:
                _documents = pickle.load(handle)
        else:
            print("Warning: DOCS_PATH not found.")
    return _model, _index, _documents

def retrieve_context(query: str, k: int = 3) -> list[str]:
    if not query.strip():
        return []

    model, index, documents = get_resources()
    
    if index is None or documents is None:
        return ["Medical knowledge base not available."]

    # Search logic
    query_embedding = model.encode([query], convert_to_numpy=True).astype("float32")
    distances, indices = index.search(query_embedding, k)

    results = []
    for idx in indices[0]:
        if idx < len(documents):
            results.append(documents[idx])
    
    return results