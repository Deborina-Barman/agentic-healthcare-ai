import os
import re
from dotenv import load_dotenv
from google import genai

from rag.retrieve_context import retrieve_context

# Load environment variables
load_dotenv()

# Check API key
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("GEMINI_API_KEY not found. Check your .env file.")

# Initialize Gemini client
client = genai.Client(api_key=API_KEY)


def patient_question_agent(
    complaint: str,
    age_gender: str | None = None
):
    """
    Patient Question Agent (LLM-powered)

    Responsibilities
    ----------------
    - Generate symptom-specific follow-up questions
    - Mimic doctor-style clinical history taking
    - Ask ONLY questions (no diagnosis, no treatment)
    """

    try:
        # ---------------------------
        # Retrieve RAG context
        # ---------------------------
        retrieved_context = retrieve_context(complaint)

        context = (
            "\n".join(retrieved_context)
            if retrieved_context
            else "No relevant medical context found."
        )

        # ---------------------------
        # Prompt
        # ---------------------------
        prompt = f"""
You are a licensed medical doctor performing clinical history-taking.

Your task:
Generate follow-up questions for a patient based on their symptom description
and the retrieved medical knowledge.

The goal is to understand the symptom better, NOT to diagnose or treat.

PATIENT CONTEXT
Age/Gender: {age_gender if age_gender else "Not specified"}

PATIENT SYMPTOM
{complaint}

MEDICAL KNOWLEDGE
{context}

STRICT RULES
- Do NOT diagnose diseases
- Do NOT suggest medicines
- Do NOT suggest tests
- Do NOT mention disease names
- Do NOT give treatment advice

INSTRUCTIONS
1. Identify the main symptom
2. Generate 3–5 follow-up questions
3. Focus on:
   - onset and duration
   - severity
   - progression
   - associated symptoms
   - red flag symptoms
4. Use simple patient-friendly language
5. Return ONLY a numbered list

Example:

1. When did the symptom start?
2. Has the pain been getting worse or staying the same?
3. Have you noticed any other symptoms?
"""

        # ---------------------------
        # Call Gemini
        # ---------------------------
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt]   # important fix
        )

        text = response.text or ""

        # ---------------------------
        # Clean response
        # ---------------------------
        questions = []

        for line in text.split("\n"):
            line = line.strip()

            if not line:
                continue

            cleaned = re.sub(r"^\d+\.\s*", "", line)

            if cleaned:
                questions.append(cleaned)

        # ---------------------------
        # Safety fallback
        # ---------------------------
        if len(questions) < 3:
            questions = [
                "When did this symptom start?",
                "Has the symptom been getting worse, improving, or staying the same?",
                "Have you noticed any other symptoms along with this problem?"
            ]

        return {"questions": questions}

    except Exception as e:
        print("Question agent error:", e)

        return {
            "questions": [
                "When did this symptom start?",
                "Has the symptom been getting worse, improving, or staying the same?",
                "Have you noticed any other symptoms along with this problem?"
            ]
        }


# ---------------------------------------------------
# MAIN TEST BLOCK
# ---------------------------------------------------

if __name__ == "__main__":

    test_complaint = "sharp abdominal pain for 3 hours"
    test_age_gender = "25 year old female"

    result = patient_question_agent(
        complaint=test_complaint,
        age_gender=test_age_gender
    )

    print("\nGenerated Follow-up Questions:\n")

    for i, q in enumerate(result["questions"], 1):
        print(f"{i}. {q}")