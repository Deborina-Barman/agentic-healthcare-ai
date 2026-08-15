import logging
import time

from services.gemini_information_extractor import (
    GeminiInformationExtractionError,
    extract_clinical_information,
)
from services.paddle_ocr_service import PaddleOCRError, read_document_with_paddle

logger = logging.getLogger(__name__)


def vision_reader_agent(image_bytes: bytes):
    """
    Vision Reader Agent

    Responsibility:
    - Read image text with PaddleOCR
    - Send only raw OCR text to Gemini for structured extraction
    - Preserve the established response wrapper for downstream consumers
    """

    total_start = time.perf_counter()
    try:
        ocr_start = time.perf_counter()
        raw_ocr_text = read_document_with_paddle(image_bytes)
        logger.info("PaddleOCR latency: %.3fs", time.perf_counter() - ocr_start)
    except PaddleOCRError as exc:
        logger.exception("PaddleOCR document-reading failure")
        logger.info("Total document processing latency: %.3fs", time.perf_counter() - total_start)
        return {
            "vision_output": {"error": {"stage": "paddle_ocr", "message": str(exc)}},
            "confidence": "low",
            "needs_patient_confirmation": True,
        }

    if not raw_ocr_text.strip():
        logger.info("Total document processing latency: %.3fs", time.perf_counter() - total_start)
        return {
            "vision_output": "No readable text detected.",
            "confidence": "low",
            "needs_patient_confirmation": True,
        }

    try:
        gemini_start = time.perf_counter()
        document_data = extract_clinical_information(raw_ocr_text)
        logger.info("Gemini extraction latency: %.3fs", time.perf_counter() - gemini_start)
    except GeminiInformationExtractionError as exc:
        logger.exception("Gemini information-extraction failure")
        logger.info("Total document processing latency: %.3fs", time.perf_counter() - total_start)
        return {
            "vision_output": {"error": {"stage": "gemini_extraction", "message": str(exc)}},
            "confidence": "low",
            "needs_patient_confirmation": True,
        }

    logger.info("Total document processing latency: %.3fs", time.perf_counter() - total_start)

    return {
        "vision_output": document_data,
        "confidence": "low",                 # handwritten = always low
        "needs_patient_confirmation": True   # always required
    }
