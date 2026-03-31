from services.gemini_vision_service import read_prescription_with_gemini


def vision_reader_agent(image_bytes: bytes):
    """
    Vision Reader Agent

    Responsibility:
    - Send prescription image to Gemini Vision
    - Return what is visible
    - Clearly mark uncertainty
    """

    vision_text = read_prescription_with_gemini(image_bytes)

    return {
        "vision_output": vision_text,
        "confidence": "low",                 # handwritten = always low
        "needs_patient_confirmation": True   # always required
    }
