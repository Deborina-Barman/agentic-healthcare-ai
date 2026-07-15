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

CASES_PATH = BASE_DIR / "fixtures" / "retrieval_queries.json"


def load_retrieval_cases(path: Path | str | None = None) -> list[dict[str, Any]]:
    cases_path = Path(path or CASES_PATH)
    with cases_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _normalize_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _safe_mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _import_retriever() -> tuple[Any | None, str | None]:
    try:
        module = importlib.import_module("followup_retriever")
    except Exception as exc:
        return None, f"Could not import followup_retriever: {exc}"
    try:
        return getattr(module, "retrieve_followup_examples"), None
    except AttributeError as exc:
        return None, f"followup_retriever.retrieve_followup_examples not found: {exc}"


def evaluate_retrieval(path: Path | str | None = None) -> dict[str, Any]:
    cases = load_retrieval_cases(path)
    retriever, import_error = _import_retriever()
    if import_error:
        return {
            "status": "skipped",
            "skipped_reason": import_error,
            "production_functions_called": ["followup_retriever.retrieve_followup_examples"],
            "case_count": len(cases),
            "precision_at_1": None,
            "precision_at_3": None,
            "recall_at_3": None,
            "hit_at_3": None,
            "mrr": None,
            "details": [],
            "failed_examples": [],
        }

    per_case_results = []
    failed_cases = []
    for case in cases:
        query = case.get("query", "")
        expected_terms = case.get("expected_terms", []) or []
        try:
            result = retriever(patient_complaint=query, top_k=3)
        except Exception as exc:
            failed_cases.append({"id": case.get("id"), "query": query, "error": str(exc)})
            result = {"success": False, "examples": []}
        if not result.get("success", False):
            failed_cases.append({"id": case.get("id"), "query": query, "error": result.get("error")})
            retrieved = []
        else:
            retrieved = [item.get("message", "") for item in result.get("examples", [])]
        hits = [example for example in retrieved if any(_normalize_text(term) in _normalize_text(example) for term in expected_terms)]
        precision_at_1 = 1.0 if retrieved[:1] and any(_normalize_text(term) in _normalize_text(retrieved[0]) for term in expected_terms) else 0.0
        precision_at_3 = len(hits) / max(1, min(3, len(retrieved))) if retrieved else 0.0
        recall_at_3 = len(hits) / max(1, len(expected_terms)) if expected_terms else 0.0
        hit_at_3 = 1.0 if hits else 0.0
        reciprocal_rank = 1.0 if retrieved and any(_normalize_text(term) in _normalize_text(retrieved[0]) for term in expected_terms) else 0.0
        per_case_results.append({"query": query, "expected_terms": expected_terms, "retrieved": retrieved, "precision_at_1": precision_at_1, "precision_at_3": precision_at_3, "recall_at_3": recall_at_3, "hit_at_3": hit_at_3, "mrr": reciprocal_rank})
        if not hits:
            failed_cases.append({"id": case.get("id"), "query": query, "error": "No expected term matched retrieved items"})

    metrics = {
        "case_count": len(per_case_results),
        "precision_at_1": _safe_mean([entry["precision_at_1"] for entry in per_case_results]),
        "precision_at_3": _safe_mean([entry["precision_at_3"] for entry in per_case_results]),
        "recall_at_3": _safe_mean([entry["recall_at_3"] for entry in per_case_results]),
        "hit_at_3": _safe_mean([entry["hit_at_3"] for entry in per_case_results]),
        "mrr": _safe_mean([entry["mrr"] for entry in per_case_results]),
    }
    return {
        "status": "evaluated" if any(entry["retrieved"] for entry in per_case_results) else "skipped",
        "production_functions_called": ["followup_retriever.retrieve_followup_examples"],
        **metrics,
        "details": per_case_results,
        "failed_examples": failed_cases,
    }


def main() -> None:
    print(json.dumps(evaluate_retrieval(), indent=2))


if __name__ == "__main__":
    main()
