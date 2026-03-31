from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

FOLLOW_UP_CATEGORIES = [
    "onset and duration",
    "severity and intensity",
    "location of symptom",
    "associated symptoms",
    "exposure or triggers",
]


def load_symptom_disease_map(input_path: Path) -> Dict[str, List[str]]:
    with input_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise ValueError("Expected the symptom-disease mapping JSON to be an object.")

    return {
        str(symptom): [str(disease) for disease in diseases]
        for symptom, diseases in data.items()
    }


def build_document(symptom: str, diseases: List[str]) -> str:
    disease_lines = "\n".join(f"- {disease}" for disease in diseases)
    follow_up_lines = "\n".join(f"- {category}" for category in FOLLOW_UP_CATEGORIES)

    return (
        f"Symptom: {symptom}\n\n"
        "Possible associated conditions:\n"
        f"{disease_lines}\n\n"
        "Clinical follow-up question categories:\n"
        f"{follow_up_lines}"
    )


def build_documents(mapping: Dict[str, List[str]]) -> List[str]:
    return [
        build_document(symptom, diseases)
        for symptom, diseases in sorted(mapping.items())
    ]


def main() -> None:
    default_input_path = Path(__file__).resolve().parents[1] / "data" / "symptom_disease_map.json"
    default_output_path = Path(__file__).resolve().parents[1] / "data" / "symcat_documents.json"

    parser = argparse.ArgumentParser(
        description="Build embedding-ready text documents from the symptom-disease map."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=default_input_path,
        help="Path to symptom_disease_map.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=default_output_path,
        help="Path to write the document list JSON.",
    )
    args = parser.parse_args()

    mapping = load_symptom_disease_map(args.input)
    documents = build_documents(mapping)

    args.output.write_text(
        json.dumps(documents, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    print(f"Wrote {len(documents)} documents to {args.output}")


if __name__ == "__main__":
    main()
