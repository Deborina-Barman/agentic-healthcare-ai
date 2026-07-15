"""
Retrieval-Augmented Clinical Follow-Up Question Retriever

Loads pre-built FAISS index and retrieves clinician-authored follow-up examples
semantically similar to patient complaints. Optimized for repeated calls using
cached global resources.
"""

from __future__ import annotations

import os
import pickle
from pathlib import Path
from typing import TypedDict

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

# =========================================================
# CONFIGURATION
# =========================================================

BASE_DIR = Path(
    r"C:\Users\debor\OneDrive\Desktop"
    r"\agentic_healthcare_ai\data"
    r"\followup_q"
)

INDEX_PATH = BASE_DIR / "followup_index.faiss"
RECORDS_PATH = BASE_DIR / "followup_records.pkl"
MODEL_NAME = "all-MiniLM-L6-v2"

# =========================================================
# GLOBAL CACHED RESOURCES
# =========================================================

_index = None
_records = None
_model = None


# =========================================================
# TYPE DEFINITIONS
# =========================================================

class FollowupExample(TypedDict, total=False):
    """Clinician-authored follow-up example"""

    message: str
    """Original patient complaint"""

    questions: list[str]
    """Clinician-authored follow-up questions"""

    ehr: str
    """Structured EHR context/medical background"""

    similarity_score: float
    """FAISS L2 similarity score (lower is better)"""


class RetrievalResult(TypedDict, total=False):
    """Result of a retrieval operation"""

    success: bool
    """Whether retrieval succeeded"""

    examples: list[FollowupExample]
    """Retrieved clinician examples"""

    error: str | None
    """Error message if retrieval failed"""


# =========================================================
# LAZY LOADERS
# =========================================================

def _load_index() -> faiss.Index | None:
    """Lazy load FAISS index from disk."""

    global _index

    if _index is not None:
        return _index

    if not INDEX_PATH.exists():
        print(
            f"WARNING: Index not found at {INDEX_PATH}"
        )
        return None

    try:
        _index = faiss.read_index(str(INDEX_PATH))
        print(f"✓ FAISS index loaded ({_index.ntotal} vectors)")
        return _index

    except Exception as e:
        print(f"ERROR loading index: {e}")
        return None


def _load_records() -> list[dict] | None:
    """Lazy load pickled records from disk."""

    global _records

    if _records is not None:
        return _records

    if not RECORDS_PATH.exists():
        print(
            f"WARNING: Records not found at {RECORDS_PATH}"
        )
        return None

    try:
        with open(RECORDS_PATH, "rb") as f:
            _records = pickle.load(f)
        print(f"✓ Records loaded ({len(_records)} records)")
        return _records

    except Exception as e:
        print(f"ERROR loading records: {e}")
        return None


def _load_model() -> SentenceTransformer | None:
    """Lazy load embedding model."""

    global _model

    if _model is not None:
        return _model

    try:
        _model = SentenceTransformer(MODEL_NAME)
        print(f"✓ Embedding model loaded ({MODEL_NAME})")
        return _model

    except Exception as e:
        print(f"ERROR loading model: {e}")
        return None


# =========================================================
# RETRIEVAL FUNCTION
# =========================================================

def retrieve_followup_examples(
    patient_complaint: str,
    top_k: int = 3,
) -> RetrievalResult:
    """
    Retrieve clinician-authored follow-up examples similar to a patient complaint.

    Performs semantic similarity search using pre-built FAISS index.
    Cached global resources optimize repeated calls.

    Parameters
    ----------
    patient_complaint : str
        Patient's clinical complaint/symptom description
    top_k : int, default=3
        Number of similar examples to retrieve

    Returns
    -------
    RetrievalResult
        Dictionary with 'success', 'examples', and optional 'error'.
        Each example includes message, questions, ehr, and similarity_score.

    Examples
    --------
    >>> result = retrieve_followup_examples("sharp chest pain for 2 hours")
    >>> if result["success"]:
    ...     for example in result["examples"]:
    ...         print(f"Example: {example['message']}")
    ...         for q in example['questions']:
    ...             print(f"  Q: {q}")
    """

    # ---------------------------------------------------
    # LOAD RESOURCES
    # ---------------------------------------------------

    try:
        model = _load_model()
        if model is None:
            raise RuntimeError("Failed to load embedding model")

        index = _load_index()
        if index is None:
            raise RuntimeError("Failed to load FAISS index")

        records = _load_records()
        if records is None:
            raise RuntimeError("Failed to load records")

    except Exception as e:
        return {
            "success": False,
            "examples": [],
            "error": f"Resource loading failed: {str(e)}",
        }

    # ---------------------------------------------------
    # VALIDATE INPUT
    # ---------------------------------------------------

    complaint_clean = (
        (patient_complaint or "")
        .strip()
    )

    if not complaint_clean:
        return {
            "success": False,
            "examples": [],
            "error": "Patient complaint cannot be empty",
        }

    # ---------------------------------------------------
    # EMBED COMPLAINT
    # ---------------------------------------------------

    try:
        embedding = model.encode(
            [complaint_clean],
            convert_to_numpy=True,
        ).astype("float32")

    except Exception as e:
        return {
            "success": False,
            "examples": [],
            "error": f"Embedding failed: {str(e)}",
        }

    # ---------------------------------------------------
    # SEARCH FAISS INDEX
    # ---------------------------------------------------

    try:
        # L2 distance: lower score = more similar
        distances, indices = index.search(
            embedding,
            min(top_k, index.ntotal),
        )

        distances = distances[0]  # Flatten
        indices = indices[0]

    except Exception as e:
        return {
            "success": False,
            "examples": [],
            "error": f"FAISS search failed: {str(e)}",
        }

    # ---------------------------------------------------
    # BUILD RESULTS
    # ---------------------------------------------------

    examples: list[FollowupExample] = []

    for idx, distance in zip(indices, distances):

        if idx >= len(records):
            continue

        record = records[idx]

        example: FollowupExample = {
            "message": record.get("message", ""),
            "questions": record.get("questions", []),
            "ehr": record.get("ehr", ""),
            "similarity_score": float(distance),
        }

        examples.append(example)

    return {
        "success": True,
        "examples": examples,
        "error": None,
    }


# =========================================================
# UTILITY FUNCTION FOR DEBUGGING
# =========================================================

def get_retriever_stats() -> dict:
    """Get statistics about loaded resources."""

    return {
        "index_loaded": _index is not None,
        "records_loaded": _records is not None,
        "model_loaded": _model is not None,
        "index_size": _index.ntotal if _index else 0,
        "records_count": len(_records) if _records else 0,
        "model_name": MODEL_NAME,
    }


# =========================================================
# TEST BLOCK
# =========================================================

if __name__ == "__main__":

    print("\n" + "=" * 60)
    print("FOLLOWUP RETRIEVER TEST")
    print("=" * 60)

    # Load resources
    print("\nLoading resources...")
    result = retrieve_followup_examples(
        patient_complaint="chest pain when breathing",
        top_k=3,
    )

    # Display results
    print(f"\nSuccess: {result['success']}")

    if result["error"]:
        print(f"Error: {result['error']}")

    else:
        print(
            f"Retrieved {len(result['examples'])} examples:\n"
        )

        for i, example in enumerate(
            result["examples"],
            1,
        ):
            print(f"[Example {i}]")
            print(
                f"Similarity Score: {example['similarity_score']:.4f}"
            )
            print(f"Message: {example['message']}")
            print("Questions:")
            for q in example["questions"][:3]:
                print(f"  • {q}")
            if example["ehr"]:
                ehr_preview = (
                    example["ehr"][:100]
                    + "..."
                    if len(example["ehr"]) > 100
                    else example["ehr"]
                )
                print(f"EHR: {ehr_preview}")
            print()

    # Stats
    print("\nRetriever Stats:")
    stats = get_retriever_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
