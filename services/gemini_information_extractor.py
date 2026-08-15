"""Convert raw OCR text into the document structure consumed by SevaCare."""

from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

_FIELDS = {
    "patient_name": "",
    "age": "",
    "gender": "",
    "diagnosis": "",
    "medicines": [],
    "dosage": [],
    "frequency": [],
    "duration": "",
    "lab_values": {},
    "clinical_notes": "",
}


class GeminiInformationExtractionError(RuntimeError):
    """Raised when Gemini cannot produce valid structured document data."""


def _empty_document() -> dict[str, Any]:
    return {
        key: value.copy() if isinstance(value, (list, dict)) else value
        for key, value in _FIELDS.items()
    }


def _normalise_document(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise GeminiInformationExtractionError("Gemini returned a non-object JSON response.")

    document = _empty_document()
    for key in document:
        if key in value and value[key] is not None:
            document[key] = value[key]

    for key in ("patient_name", "age", "gender", "diagnosis", "duration", "clinical_notes"):
        document[key] = str(document[key])
    for key in ("medicines", "dosage", "frequency"):
        if not isinstance(document[key], list):
            document[key] = [str(document[key])] if document[key] else []
        else:
            document[key] = [str(item) for item in document[key]]
    if not isinstance(document["lab_values"], dict):
        document["lab_values"] = {}
    else:
        document["lab_values"] = {
            str(name): str(result) for name, result in document["lab_values"].items()
        }
    return document


def extract_clinical_information(raw_ocr_text: str) -> dict[str, Any]:
    """Use Gemini on OCR text only, never on the source image."""
    if not raw_ocr_text or not raw_ocr_text.strip():
        raise GeminiInformationExtractionError("No OCR text was provided for extraction.")

    prompt = f"""You are a medical-document information extraction service.
Convert the OCR text below into JSON with exactly these keys:
patient_name, age, gender, diagnosis, medicines, dosage, frequency, duration,
lab_values, clinical_notes.

Rules:
- Extract only text explicitly present in the OCR input; do not infer or diagnose.
- Use empty strings, empty arrays, or an empty object for unavailable fields.
- medicines, dosage, and frequency must be arrays of strings.
- lab_values must be an object mapping the visibly written test name to its value.
- Return JSON only, without Markdown.

OCR text:
---
{raw_ocr_text}
---"""

    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        response_text = response.text if response else ""
        if not response_text:
            raise GeminiInformationExtractionError("Gemini returned an empty response.")
        return _normalise_document(json.loads(response_text))
    except GeminiInformationExtractionError:
        raise
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise GeminiInformationExtractionError(
            f"Gemini returned invalid structured data: {exc}"
        ) from exc
    except Exception as exc:
        raise GeminiInformationExtractionError(
            f"Gemini information extraction failed: {exc}"
        ) from exc
