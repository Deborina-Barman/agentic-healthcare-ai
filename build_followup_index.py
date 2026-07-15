from __future__ import annotations

import pickle
from pathlib import Path

import faiss
import numpy as np
import pandas as pd

from sentence_transformers import (
    SentenceTransformer,
)

# ---------------------------------------------------
# PATHS
# ---------------------------------------------------

DATASET_PATH = (
    r"C:\Users\debor\OneDrive\Desktop"
    r"\agentic_healthcare_ai\data"
    r"\followup_q\train-00000-of-00001.parquet"
)

BASE_DIR = Path(
    r"C:\Users\debor\OneDrive\Desktop"
    r"\agentic_healthcare_ai\data"
    r"\followup_q"
)

INDEX_PATH = (
    BASE_DIR
    / "followup_index.faiss"
)

RECORDS_PATH = (
    BASE_DIR
    / "followup_records.pkl"
)

MODEL_NAME = "all-MiniLM-L6-v2"

# ---------------------------------------------------
# LOAD DATASET
# ---------------------------------------------------

print("Loading Followup-Q dataset...")

df = pd.read_parquet(DATASET_PATH)

print(f"Dataset loaded: {len(df)} rows")

# ---------------------------------------------------
# CLEAN PATIENT MESSAGES
# ---------------------------------------------------

messages = (
    df["Message"]
    .fillna("")
    .astype(str)
    .tolist()
)

# ---------------------------------------------------
# LOAD EMBEDDING MODEL
# ---------------------------------------------------

print("Loading embedding model...")

model = SentenceTransformer(MODEL_NAME)

# ---------------------------------------------------
# CREATE EMBEDDINGS
# ---------------------------------------------------

print("Generating embeddings...")

embeddings = model.encode(
    messages,
    convert_to_numpy=True,
    show_progress_bar=True,
).astype("float32")

print(
    f"Embeddings shape: {embeddings.shape}"
)

# ---------------------------------------------------
# CREATE FAISS INDEX
# ---------------------------------------------------

print("Creating FAISS index...")

dimension = embeddings.shape[1]

index = faiss.IndexFlatL2(dimension)

index.add(embeddings)

print(
    f"FAISS index contains {index.ntotal} vectors"
)

# ---------------------------------------------------
# SAVE FAISS INDEX
# ---------------------------------------------------

faiss.write_index(
    index,
    str(INDEX_PATH),
)

print(
    f"FAISS index saved to:\n{INDEX_PATH}"
)

# ---------------------------------------------------
# PREPARE RECORDS
# ---------------------------------------------------

print("Preparing records...")

records = []

for _, row in df.iterrows():

    try:

        questions = row["Questions"]

        if isinstance(
            questions,
            np.ndarray,
        ):
            questions = questions.tolist()

        elif not isinstance(
            questions,
            list,
        ):
            questions = [str(questions)]

        records.append({

            "message":
                str(
                    row["Message"]
                ),

            "questions":
                questions,

            "ehr":
                str(
                    row["EHR"]
                ),
        })

    except Exception as exc:

        print(
            "Skipping bad row:",
            exc,
        )

# ---------------------------------------------------
# SAVE RECORDS
# ---------------------------------------------------

with open(
    RECORDS_PATH,
    "wb",
) as f:

    pickle.dump(
        records,
        f,
    )

print(
    f"Records saved to:\n{RECORDS_PATH}"
)

# ---------------------------------------------------
# SUCCESS
# ---------------------------------------------------

print("\nFollowup-Q index created successfully.")
print(
    f"Total records stored: {len(records)}"
)