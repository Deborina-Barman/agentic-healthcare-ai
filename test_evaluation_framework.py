import json
from pathlib import Path

from evaluation.evaluate_nlice import load_dataset, compute_classification_metrics
from evaluation.evaluate_retrieval import load_retrieval_cases


def test_dataset_and_metrics_helpers():
    base = Path(__file__).resolve().parent / "evaluation"
    dataset = load_dataset(base / "test_cases" / "dataset.json")
    assert isinstance(dataset, list)
    assert len(dataset) >= 5

    predictions = ["high", "low", "high"]
    labels = ["high", "low", "medium"]
    metrics = compute_classification_metrics(predictions, labels)
    assert metrics["accuracy"] == 1.0
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1"] == 1.0

    retrieval_cases = load_retrieval_cases(base / "test_cases" / "retrieval_cases.json")
    assert len(retrieval_cases) >= 1
