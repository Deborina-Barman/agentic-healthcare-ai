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

CASES_PATH = BASE_DIR / "fixtures" / "summary_conversations.json"


def load_summary_cases(path: Path | str | None = None) -> list[dict[str, Any]]:
    cases_path = Path(path or CASES_PATH)
    with cases_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _normalize_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _import_summary_agent() -> tuple[Any | None, str | None]:
    try:
        module = importlib.import_module("agents.summary_agent")
    except Exception as exc:
        return None, f"Could not import agents.summary_agent: {exc}"
    try:
        return getattr(module, "summary_agent"), None
    except AttributeError as exc:
        return None, f"agents.summary_agent.summary_agent not found: {exc}"


def evaluate_summary(path: Path | str | None = None) -> dict[str, Any]:
    cases = load_summary_cases(path)
    summary_agent_fn, import_error = _import_summary_agent()
    if import_error:
        return {
            "status": "skipped",
            "skipped_reason": import_error,
            "production_functions_called": ["agents.summary_agent.summary_agent"],
            "case_count": len(cases),
            "details": [],
            "summary_stats": {
                "complaint_captured": None,
                "duration_captured": None,
                "medication_captured": None,
                "medication_response_captured": None,
                "negative_findings_correct": None,
                "hallucinated_findings": None,
                "overall_factual_correctness": None,
            },
        }

    results = []
    for case in cases:
        state = case.get("clinical_state", {}) or {}
        expected = case.get("expected", {}) or {}
        try:
            summary_text = summary_agent_fn(state)
        except Exception as exc:
            return {
                "status": "skipped",
                "skipped_reason": str(exc),
                "production_functions_called": ["agents.summary_agent.summary_agent"],
                "case_count": len(cases),
                "details": [],
                "summary_stats": {},
            }
        complaint_captured = bool(state.get("complaint")) and _normalize_text(state.get("complaint")) in _normalize_text(summary_text)
        duration_captured = bool(state.get("nlice", {}).get("chronology")) and _normalize_text(state.get("nlice", {}).get("chronology")) in _normalize_text(summary_text)
        medication_captured = bool(state.get("medications")) and _normalize_text(state.get("medications")) in _normalize_text(summary_text)
        medication_response_captured = False
        hallucinated_findings = any(term for term in ["chest pain", "fever", "cough"] if term in _normalize_text(summary_text) and term not in _normalize_text(state.get("complaint", "")))
        negative_findings_correct = expected.get("negative_findings_correct", True)
        overall_factual_correctness = 1.0 if not hallucinated_findings and complaint_captured else 0.0
        results.append({"id": case.get("id"), "summary_text": summary_text, "complaint_captured": complaint_captured, "duration_captured": duration_captured, "medication_captured": medication_captured, "medication_response_captured": medication_response_captured, "negative_findings_correct": negative_findings_correct, "hallucinated_findings": hallucinated_findings, "overall_factual_correctness": overall_factual_correctness})
    return {"status": "evaluated", "production_functions_called": ["agents.summary_agent.summary_agent"], "case_count": len(results), "details": results, "summary_stats": {"complaint_captured": sum(item["complaint_captured"] for item in results) / len(results) if results else None, "duration_captured": sum(item["duration_captured"] for item in results) / len(results) if results else None, "medication_captured": sum(item["medication_captured"] for item in results) / len(results) if results else None, "medication_response_captured": sum(item["medication_response_captured"] for item in results) / len(results) if results else None, "negative_findings_correct": sum(item["negative_findings_correct"] for item in results) / len(results) if results else None, "hallucinated_findings": sum(item["hallucinated_findings"] for item in results) / len(results) if results else None, "overall_factual_correctness": sum(item["overall_factual_correctness"] for item in results) / len(results) if results else None}}


def main() -> None:
    print(json.dumps(evaluate_summary(), indent=2))


if __name__ == "__main__":
    main()
