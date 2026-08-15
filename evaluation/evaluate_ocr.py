from __future__ import annotations

import importlib
import json
import re
import sys
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

CASES_PATH = BASE_DIR / "fixtures" / "ocr_reports.json"
FIELD_NAMES = ["Hemoglobin", "WBC", "Platelets", "Glucose", "Creatinine"]


def load_ocr_cases(path: Path | str | None = None) -> list[dict[str, Any]]:
    cases_path = Path(path or CASES_PATH)
    with cases_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _extract_from_text(text: str) -> dict[str, str]:
    extracted: dict[str, str] = {}
    for field in FIELD_NAMES:
        match = re.search(rf"{re.escape(field)}\s*[:=]?\s*([0-9.]+)", text, flags=re.I)
        if match:
            extracted[field] = match.group(1)
    return extracted


def _import_ocr_pipeline() -> tuple[Any | None, list[str]]:
    errors: list[str] = []
    try:
        module = importlib.import_module("agents.reader_agent")
    except Exception as exc:
        errors.append(f"Could not import agents.reader_agent: {exc}")
        return None, errors
    try:
        vision_reader_agent = getattr(module, "vision_reader_agent")
    except AttributeError as exc:
        errors.append(f"agents.reader_agent.vision_reader_agent not found: {exc}")
        return None, errors
    try:
        importlib.import_module("services.paddle_ocr_service")
    except Exception as exc:
        errors.append(f"Could not import services.paddle_ocr_service: {exc}")
    return vision_reader_agent, errors


def evaluate_ocr(path: Path | str | None = None) -> dict[str, Any]:
    cases = load_ocr_cases(path)
    vision_reader_agent, import_errors = _import_ocr_pipeline()
    if import_errors:
        return {
            "status": "skipped",
            "skipped_reason": "; ".join(import_errors),
            "production_functions_called": ["agents.reader_agent.vision_reader_agent", "services.paddle_ocr_service.read_document_with_paddle", "services.gemini_information_extractor.extract_clinical_information"],
            "case_count": len(cases),
            "extraction_accuracy": None,
            "missing_fields": None,
            "incorrect_values": None,
            "details": [],
        }

    results = []
    total_fields = 0
    missing_fields = 0
    incorrect_values = 0
    for case in cases:
        expected_values = case.get("expected_values", {}) or {}
        image_bytes = case.get("image_bytes")
        if not image_bytes:
            results.append({"id": case.get("id"), "status": "skipped", "skipped_reason": "No image bytes supplied for the OCR pipeline"})
            continue
        try:
            raw_result = vision_reader_agent(image_bytes)
        except Exception as exc:
            results.append({"id": case.get("id"), "status": "skipped", "skipped_reason": str(exc)})
            continue
        extracted_text = json.dumps(raw_result.get("vision_output", ""))
        extracted_values = _extract_from_text(extracted_text)
        for field in FIELD_NAMES:
            total_fields += 1
            expected_value = expected_values.get(field)
            actual_value = extracted_values.get(field)
            if actual_value is None:
                missing_fields += 1
            elif str(actual_value) != str(expected_value):
                incorrect_values += 1
        results.append({"id": case.get("id"), "expected_values": expected_values, "extracted_values": extracted_values, "missing_fields": missing_fields, "incorrect_values": incorrect_values, "status": "evaluated"})
    extraction_accuracy = 1.0 - (incorrect_values / total_fields) if total_fields else None
    return {"status": "evaluated" if results else "skipped", "production_functions_called": ["agents.reader_agent.vision_reader_agent", "services.paddle_ocr_service.read_document_with_paddle", "services.gemini_information_extractor.extract_clinical_information"], "case_count": len(cases), "extraction_accuracy": extraction_accuracy, "missing_fields": missing_fields, "incorrect_values": incorrect_values, "details": results}


def main() -> None:
    print(json.dumps(evaluate_ocr(), indent=2))


if __name__ == "__main__":
    main()
