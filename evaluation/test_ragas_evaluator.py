from __future__ import annotations

from evaluation.evaluate_ragas import build_ragas_dataset


def test_build_ragas_dataset_uses_existing_fixtures() -> None:
    dataset = build_ragas_dataset()
    assert isinstance(dataset, list)
    assert dataset
    first = dataset[0]
    assert "user_query" in first
    assert "missing_clinical_field" in first
    assert "retrieved_contexts" in first
    assert "generated_followup_question" in first
    assert "expected_followup_question" in first
