from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

DATASET_PATH = BASE_DIR / "fixtures" / "urgency_cases.json"


def load_dataset(path: Path | str | None = None) -> list[dict[str, Any]]:
    dataset_path = Path(path or DATASET_PATH)
    with dataset_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _normalize_label(value: Any) -> str:
    return str(value or "").strip().upper()


def _import_urgency_agent() -> tuple[Any | None, str | None]:
    try:
        module = importlib.import_module("agents.urgency_classifier_agent")
    except Exception as exc:
        return None, f"Could not import agents.urgency_classifier_agent: {exc}"
    try:
        return getattr(module, "urgency_classifier_agent"), None
    except AttributeError as exc:
        return None, f"agents.urgency_classifier_agent.urgency_classifier_agent not found: {exc}"


def evaluate_urgency(path: Path | str | None = None) -> dict[str, Any]:
    dataset = load_dataset(path)
    urgency_classifier_agent, import_error = _import_urgency_agent()
    if import_error:
        return {
            "status": "skipped",
            "skipped_reason": import_error,
            "production_functions_called": ["agents.urgency_classifier_agent.urgency_classifier_agent"],
            "dataset_size": len(dataset),
            "accuracy": None,
            "confusion_matrix": None,
            "precision": None,
            "recall": None,
            "f1": None,
            "details": [],
        }

    labels = []
    predictions = []
    details = []
    for item in dataset:
        state = item.get("state", {}) or {}
        expected_label = _normalize_label(item.get("expected_label"))
        try:
            result = urgency_classifier_agent(state)
            predicted_label = _normalize_label(result.get("urgency_level") or result.get("urgency"))
        except Exception as exc:
            details.append({"id": item.get("id"), "status": "skipped", "skipped_reason": str(exc)})
            continue
        labels.append(expected_label)
        predictions.append(predicted_label)
        details.append({"id": item.get("id"), "expected": expected_label, "predicted": predicted_label, "state": state, "status": "evaluated"})

    if not predictions:
        return {
            "status": "skipped",
            "skipped_reason": "No urgency predictions could be produced",
            "production_functions_called": ["agents.urgency_classifier_agent.urgency_classifier_agent"],
            "dataset_size": len(dataset),
            "accuracy": None,
            "confusion_matrix": None,
            "precision": None,
            "recall": None,
            "f1": None,
            "details": details,
        }

    try:
        from sklearn.metrics import accuracy_score, confusion_matrix, precision_score, recall_score, f1_score
    except Exception as exc:
        return {
            "status": "skipped",
            "skipped_reason": f"scikit-learn unavailable: {exc}",
            "production_functions_called": ["agents.urgency_classifier_agent.urgency_classifier_agent"],
            "dataset_size": len(dataset),
            "accuracy": None,
            "confusion_matrix": None,
            "precision": None,
            "recall": None,
            "f1": None,
            "details": details,
        }

    return {
        "status": "evaluated",
        "production_functions_called": ["agents.urgency_classifier_agent.urgency_classifier_agent"],
        "dataset_size": len(dataset),
        "accuracy": float(accuracy_score(labels, predictions)) if labels else None,
        "confusion_matrix": confusion_matrix(labels, predictions, labels=["LOW", "MODERATE", "HIGH", "EMERGENCY"]).tolist() if labels else None,
        "precision": float(precision_score(labels, predictions, average="macro", zero_division=0)) if labels else None,
        "recall": float(recall_score(labels, predictions, average="macro", zero_division=0)) if labels else None,
        "f1": float(f1_score(labels, predictions, average="macro", zero_division=0)) if labels else None,
        "details": details,
    }


def main() -> None:
    print(json.dumps(evaluate_urgency(), indent=2))


if __name__ == "__main__":
    main()
