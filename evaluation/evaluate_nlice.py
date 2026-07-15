from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

DATASET_PATH = BASE_DIR / "fixtures" / "nlice_cases.json"


def load_dataset(path: Path | str | None = None) -> list[dict[str, Any]]:
    dataset_path = Path(path or DATASET_PATH)
    with dataset_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _normalize_label(value: Any) -> str:
    return str(value or "").strip().lower()


def _import_production_function() -> tuple[Any | None, str | None]:
    try:
        module = importlib.import_module("chat_controller")
    except Exception as exc:
        return None, f"Could not import chat_controller: {exc}"
    try:
        return getattr(module, "extract_info_node"), None
    except AttributeError as exc:
        return None, f"chat_controller.extract_info_node not found: {exc}"


def compute_classification_metrics(predictions: Iterable[str], labels: Iterable[str]) -> dict[str, float | None] | None:
    prediction_list = [_normalize_label(value) for value in predictions]
    label_list = [_normalize_label(value) for value in labels]
    if not prediction_list or len(prediction_list) != len(label_list):
        return None
    try:
        from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
    except Exception as exc:
        raise RuntimeError(f"scikit-learn unavailable: {exc}") from exc
    return {
        "accuracy": float(accuracy_score(label_list, prediction_list)),
        "precision": float(precision_score(label_list, prediction_list, average="macro", zero_division=0)),
        "recall": float(recall_score(label_list, prediction_list, average="macro", zero_division=0)),
        "f1": float(f1_score(label_list, prediction_list, average="macro", zero_division=0)),
        "note": None,
    }


def evaluate_nlice_extraction(path: Path | str | None = None) -> dict[str, Any]:
    dataset = load_dataset(path)
    extract_info_node, import_error = _import_production_function()
    if import_error:
        return {
            "status": "skipped",
            "skipped_reason": import_error,
            "production_functions_called": ["chat_controller.extract_info_node"],
            "dataset_size": len(dataset),
            "metrics": None,
            "details": [],
            "confusion_details": [],
        }

    predictions = []
    labels = []
    details = []
    confusion_details = []

    for item in dataset:
        expected = item.get("expected_nlice", {}) or {}
        state = {"messages": [{"role": "user", "content": item.get("patient_utterance", "")}]}
        try:
            result = extract_info_node(state)
            nlice_data = result.get("nlice_data") or {}
            predicted = {
                "nature": str(nlice_data.get("nature", "")).strip().lower() or "unknown",
                "location": str(nlice_data.get("location", "")).strip().lower() or "unknown",
                "chronology": str(nlice_data.get("chronology", "")).strip().lower() or "unknown",
            }
        except Exception as exc:
            details.append({"id": item.get("id"), "status": "skipped", "skipped_reason": str(exc)})
            continue

        for field in ("nature", "location", "chronology"):
            labels.append(_normalize_label(expected.get(field, "unknown")))
            predictions.append(_normalize_label(predicted.get(field, "unknown")))
            if _normalize_label(expected.get(field, "unknown")) != _normalize_label(predicted.get(field, "unknown")):
                confusion_details.append({
                    "id": item.get("id"),
                    "field": field,
                    "expected": expected.get(field, "unknown"),
                    "predicted": predicted.get(field, "unknown"),
                    "patient_utterance": item.get("patient_utterance"),
                })
        details.append({
            "id": item.get("id"),
            "patient_utterance": item.get("patient_utterance"),
            "expected": expected,
            "predicted": predicted,
            "status": "evaluated",
        })

    try:
        metrics = compute_classification_metrics(predictions, labels)
    except Exception as exc:
        return {
            "status": "skipped",
            "skipped_reason": str(exc),
            "production_functions_called": ["chat_controller.extract_info_node"],
            "dataset_size": len(dataset),
            "metrics": None,
            "details": details,
            "confusion_details": confusion_details,
        }

    return {
        "status": "evaluated" if metrics is not None else "skipped",
        "production_functions_called": ["chat_controller.extract_info_node"],
        "dataset_size": len(dataset),
        "metrics": metrics,
        "details": details,
        "confusion_details": confusion_details,
    }


def main() -> None:
    result = evaluate_nlice_extraction()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
