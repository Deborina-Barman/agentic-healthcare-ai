import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def clinical_context_agent(state: dict):
    """
    Clinical Context Agent

    Purpose:
    - Provide AI-assisted clinical context for doctors
    - Highlight possible condition categories and considerations
    - DO NOT diagnose
    - DO NOT recommend treatment or medicines
    """

    complaint = state.get("complaint", "")
    vision_data = state.get("vision_output") or {}
    vision_output = vision_data.get("vision_output", "")
    patient_answers = state.get("patient_answers") or {}
    safety_flags = state.get("safety_flags", [])

    prompt = (
        "You are an AI assistant helping a medical doctor by summarizing "
        "clinical context based on patient-reported information.\n\n"
        "STRICT RULES:\n"
        "- Do NOT diagnose any disease.\n"
        "- Do NOT prescribe or recommend medicines.\n"
        "- Do NOT state certainty.\n"
        "- Use words like 'may', 'commonly considered', 'could include'.\n"
        "- This is NOT medical advice.\n\n"
        "PATIENT INFORMATION:\n"
        f"- Complaint: {complaint}\n"
        f"- Prescription text (if any): {vision_output}\n"
        f"- Patient answers: {patient_answers}\n"
        f"- Safety flags: {safety_flags}\n\n"
        "TASK:\n"
        "Provide a short clinical context section for a doctor, including:\n"
        "1. Possible condition categories commonly considered\n"
        "2. Key clinical considerations\n"
        "3. Any red flags or points needing attention\n\n"
        "OUTPUT FORMAT:\n"
        "Clinical Context (AI-assisted, non-diagnostic):\n"
        "- Possible considerations:\n"
        "- Key clinical points:\n"
        "- Notes / cautions:\n"
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[prompt],
    )

    return {
        "clinical_context": response.text if response and response.text else "Clinical context not available."
    }
