"""Raw document text extraction using PaddleOCR."""

from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from typing import Any

import numpy as np
from PIL import Image


class PaddleOCRError(RuntimeError):
    """Raised when a document cannot be processed by PaddleOCR."""


@lru_cache(maxsize=1)
def _get_ocr_engine() -> Any:
    """Create one OCR engine per process; model loading is expensive."""
    try:
        from paddleocr import PaddleOCR
    except ImportError as exc:
        raise PaddleOCRError(
            "PaddleOCR is not installed. Install the project requirements first."
        ) from exc

    try:
        return PaddleOCR(use_angle_cls=True, lang="en")
    except Exception as exc:
        raise PaddleOCRError(f"Could not initialize PaddleOCR: {exc}") from exc


def read_document_with_paddle(image_bytes: bytes) -> str:
    """Return only the text visible in *image_bytes*; performs no interpretation."""
    if not image_bytes:
        raise PaddleOCRError("No image data was provided for OCR.")

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            document_image = np.array(image.convert("RGB"))
    except Exception as exc:
        raise PaddleOCRError(f"Invalid or unsupported image data: {exc}") from exc

    try:
        result = _get_ocr_engine().ocr(document_image, cls=True)
    except PaddleOCRError:
        raise
    except Exception as exc:
        raise PaddleOCRError(f"PaddleOCR failed to read the document: {exc}") from exc

    lines: list[str] = []
    # PaddleOCR v2 returns one result list per image, with [box, (text, score)]
    # entries. Keep only text so this service remains OCR-only.
    for page in result or []:
        if not page:
            continue
        for line in page:
            try:
                text = str(line[1][0]).strip()
            except (IndexError, KeyError, TypeError):
                continue
            if text:
                lines.append(text)

    return "\n".join(lines)
