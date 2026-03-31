import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def complaint_agent(patient_text: str):
    """
    Complaint Agent

    Responsibility:
    - Clean patient-written complaint
    - Convert to structured, doctor-friendly format
    - Do NOT diagnose
    """

    prompt = (
        "You are a medical assistant helping a doctor understand a patient's complaint.\n\n"
        "Rules:\n"
        "- Do NOT diagnose.\n"
        "- Do NOT suggest treatment.\n"
        "- Only organize the complaint clearly.\n"
        "- Use simple clinical language.\n\n"
        "Patient complaint:\n"
        f"{patient_text}\n\n"
        "Output format:\n"
        "- Primary complaint\n"
        "- Associated symptoms\n"
        "- Duration (if mentioned)\n"
        "- Severity (if mentioned)\n"
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[prompt],
    )

    return response.text
