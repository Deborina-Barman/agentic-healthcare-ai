from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Set


def _candidate_disease_columns(symptom_column: str) -> Iterable[str]:
    prefix = symptom_column[: -len("_symptoms_name")]
    yield f"{prefix}_disorder_name"
    yield f"{prefix}_symptoms_disorder"


def build_symptom_disease_map(csv_path: Path) -> Dict[str, List[str]]:
    symptom_to_diseases: dict[str, Set[str]] = defaultdict(set)

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"No headers found in {csv_path}")

        symptom_columns = [
            name for name in reader.fieldnames if name.endswith("_symptoms_name")
        ]

        for row in reader:
            for symptom_column in symptom_columns:
                symptom = (row.get(symptom_column) or "").strip()
                if not symptom:
                    continue

                disease = ""
                for disease_column in _candidate_disease_columns(symptom_column):
                    disease = (row.get(disease_column) or "").strip()
                    if disease:
                        break

                if disease:
                    symptom_to_diseases[symptom].add(disease)

    return {
        symptom: sorted(diseases)
        for symptom, diseases in sorted(symptom_to_diseases.items())
    }


def main() -> None:
    default_csv_path = Path(__file__).resolve().parents[1] / "data" / "symcat-801-diseases.csv"

    parser = argparse.ArgumentParser(
        description="Build a symptom-to-diseases mapping from the Symcat diseases CSV."
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=default_csv_path,
        help="Path to symcat-801-diseases.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write the mapping as JSON.",
    )
    args = parser.parse_args()

    mapping = build_symptom_disease_map(args.csv)

    if args.output:
        args.output.write_text(
            json.dumps(mapping, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
        print(f"Wrote {len(mapping)} symptoms to {args.output}")
    else:
        print(json.dumps(mapping, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
