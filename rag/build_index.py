from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import List

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


def load_documents(input_path: Path) -> List[str]:
    """Load the embedding-ready medical documents from JSON."""
    with input_path.open("r", encoding="utf-8") as handle:
        documents = json.load(handle)

    if not isinstance(documents, list) or not all(
        isinstance(document, str) for document in documents
    ):
        raise ValueError("Expected a JSON array of document strings.")

    return documents


def build_faiss_index(documents: List[str], model_name: str) -> tuple[faiss.IndexFlatL2, np.ndarray]:
    """Generate embeddings for the documents and store them in a FAISS index."""
    # Load the sentence-transformers model used to convert text into vectors.
    model = SentenceTransformer(model_name)

    # Encode all documents in one batch and force float32 for FAISS compatibility.
    embeddings = model.encode(
        documents,
        convert_to_numpy=True,
        show_progress_bar=True,
    ).astype("float32")

    # Create a flat L2 index sized to the embedding dimension.
    index = faiss.IndexFlatL2(embeddings.shape[1])

    # Add every document embedding into the FAISS index.
    index.add(embeddings)

    return index, embeddings


def save_outputs(index: faiss.IndexFlatL2, documents: List[str], index_path: Path, docs_path: Path) -> None:
    """Save the FAISS index and the source documents for later retrieval."""
    faiss.write_index(index, str(index_path))

    with docs_path.open("wb") as handle:
        pickle.dump(documents, handle)


def main() -> None:
    base_dir = Path(__file__).resolve().parents[1] / "data"
    input_path = base_dir / "symcat_documents.json"
    index_path = base_dir / "symcat_index.faiss"
    docs_path = base_dir / "symcat_docs.pkl"
    model_name = "all-MiniLM-L6-v2"

    # Step 1: Load the text documents that will be embedded and indexed.
    documents = load_documents(input_path)
    if not documents:
        raise ValueError(f"No documents found in {input_path}")

    # Steps 2-6: Create embeddings, convert them to numpy, build FAISS, and add vectors.
    index, embeddings = build_faiss_index(documents, model_name)

    # Save both the FAISS index and the original documents needed during retrieval.
    save_outputs(index, documents, index_path, docs_path)

    print(
        f"Indexed {len(documents)} documents with dimension {embeddings.shape[1]} "
        f"using {model_name}."
    )
    print(f"Saved FAISS index to {index_path}")
    print(f"Saved source documents to {docs_path}")


if __name__ == "__main__":
    main()
