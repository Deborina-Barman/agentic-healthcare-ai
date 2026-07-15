import json
import os
import re

from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def _normalize_text(value, default="unknown") -> str:
    text = str(value).strip() if value is not None else ""
    return text or default


def _normalize_intensity(value) -> int:
    if isinstance(value, (int, float)):
        return int(value)

    text = str(value).strip() if value is not None else ""
    match = re.search(r"\d+", text)
    if match:
        return int(match.group())
    return 5


def _normalize_output(parsed: dict, complaint: str) -> dict:
    nlice_data = parsed.get("nlice") or {}
    nlice = nlice_data if isinstance(nlice_data, dict) else {}
    normalized_intensity = _normalize_intensity(nlice.get("intensity"))

    return {
        "chief_complaint": _normalize_text(parsed.get("chief_complaint", complaint)),
        "nlice": {
            "nature": _normalize_text(nlice.get("nature")),
            "location": _normalize_text(nlice.get("location")),
            "intensity": int(normalized_intensity),
            "chronology": _normalize_text(nlice.get("chronology")),
            "excitation": _normalize_text(nlice.get("excitation")),
        },
        "associated_symptoms": parsed.get("associated_symptoms", []),
        "risk_flags": parsed.get("risk_flags", []),
        "clinical_summary": _normalize_text(parsed.get("clinical_summary")),
    }


def clinical_synthesis_agent(state: dict):
    """
    Clinical Synthesis Agent

    Purpose:
    - Structure patient-reported symptom information into an NLICE summary
    - Keep the output non-diagnostic and treatment-free
    - Produce a consistent JSON shape for downstream agents
    """

    complaint = state.get("complaint", "")
    patient_answers = state.get("patient_answers") or {}
    age_gender = state.get("age_gender", "")

    # NLICE helps structure symptom information in a clinically meaningful way.
    # It organizes free-text symptom descriptions into a format that is easier
    # to review and summarize without diagnosing or recommending treatment.
    prompt = f"""
You are an AI medical documentation assistant.

Your job is to convert patient-reported symptom information into structured NLICE symptom modeling.

NLICE stands for:
- N - Nature of symptom
- L - Location
- I - Intensity
- C - Chronology (time or duration)
- E - Excitation (what worsens or improves the symptom)

STRICT RULES:
- Do NOT diagnose diseases.
- Do NOT suggest treatment.
- Do NOT recommend medicines, tests, or next steps.
- Only structure and summarize the patient symptom information.
- If any NLICE text field is not clearly available, return "unknown".
- "intensity" must be an integer.
- If intensity is written as text like "8/10", extract the number and return 8.
- If intensity is missing or unclear, return 5.

PATIENT INFORMATION:
- Age/Gender: {age_gender}
- Chief complaint: {complaint}
- Patient answers: {patient_answers}

Return ONLY valid JSON in this exact structure:
{{
  "chief_complaint": "",
  "nlice": {{
    "nature": "unknown",
    "location": "unknown",
    "intensity": 5,
    "chronology": "unknown",
    "excitation": "unknown"
  }},
  "associated_symptoms": [],
  "risk_flags": [],
  "clinical_summary": ""
}}

The "clinical_summary" must be a short non-diagnostic summary of the symptom pattern only.
"""

    fallback = {
        "chief_complaint": complaint or "unknown",
        "nlice": {
            "nature": "unknown",
            "location": "unknown",
            "intensity": 5,
            "chronology": "unknown",
            "excitation": "unknown",
        },
        "associated_symptoms": [],
        "risk_flags": [],
        "clinical_summary": "unknown",
    }

    try:
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=[prompt],
        )

        raw_text = response.text.strip() if response and response.text else ""
        if raw_text.startswith("```"):
            raw_text = raw_text.strip("`")
            if raw_text.lower().startswith("json"):
                raw_text = raw_text[4:].strip()

        parsed = json.loads(raw_text)

        return _normalize_output(parsed, complaint)
    except Exception as e:
        print("Clinical synthesis agent error:", e)
        return fallback


def main():
    example_state = {
        "complaint": "Severe abdominal pain",
        "age_gender": "28-year-old female",
        "patient_answers": {
            "When did the symptom start?": "3 hours ago",
            "How severe is the pain?": "8/10",
            "Where is the pain located?": "lower abdomen",
            "What type of pain is it?": "sharp",
            "Does anything make it worse?": "movement",
        },
    }

    result = clinical_synthesis_agent(example_state)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
