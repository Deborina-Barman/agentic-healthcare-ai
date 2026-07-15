"""
Retrieval-Augmented Clinical Exploration Agent.

This agent asks clinician-style triage exploration questions that sit beside
NLICE. The graph still controls when to ask and when to stop; this module only
generates the next natural question for a deterministic exploration focus.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import TypedDict

from dotenv import load_dotenv
from google import genai

parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from followup_retriever import retrieve_followup_examples


load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError(
        "GEMINI_API_KEY not found. Check your .env file."
    )

client = genai.Client(api_key=API_KEY)


class ClinicalExplorationResult(TypedDict, total=False):
    success: bool
    question: str
    focus: str
    source: str
    error: str | None
    retrieved_examples: list[dict] | None


FOCUS_GUIDANCE = {
    "associated_symptoms": (
        "Explore clinically relevant associated symptoms for the complaint."
    ),
    "red_flags": (
        "Screen for safety-relevant warning symptoms without alarming the patient."
    ),
    "contextual_followup": (
        "Ask the next clinician-style contextual question based on the patient's "
        "last answer and retrieved examples."
    ),
    "nlice_blend": (
        "Ask a natural question that advances NLICE completeness while still "
        "feeling like clinical exploration."
    ),
}


def _format_nlice_state(
    nlice_state: dict | None,
) -> str:

    nlice = nlice_state or {}
    fields = (
        "nature",
        "location",
        "intensity",
        "chronology",
        "excitation",
    )

    lines = []
    for field in fields:
        value = nlice.get(field) or "Missing"
        lines.append(f"- {field}: {value}")

    return "\n".join(lines)


def _format_examples(
    examples: list[dict] | None,
) -> str:

    if not examples:
        return "(No retrieved examples available.)"

    blocks = []
    for index, example in enumerate(examples[:4], 1):
        lines = [
            f"[Example {index}]",
            f"Patient complaint: {example.get('message', '')}",
        ]

        questions = example.get("questions") or []
        if questions:
            lines.append("Clinician questions:")
            for question in questions[:5]:
                lines.append(f"- {question}")

        ehr = (example.get("ehr") or "").strip()
        if ehr:
            lines.append(f"EHR context: {ehr[:220]}")

        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)


def _format_context(
    conversation_context: list[dict[str, str]] | None,
) -> str:

    if not conversation_context:
        return "(None yet)"

    lines = []
    for turn in conversation_context[-8:]:
        role = turn.get("role", "message")
        content = turn.get("content", "")
        if content:
            lines.append(f"{role}: {content}")

    return "\n".join(lines) if lines else "(None yet)"


def _build_exploration_prompt(
    complaint: str,
    focus: str,
    nlice_state: dict | None,
    associated_symptoms: list[str] | None,
    missing_nlice_fields: list[str] | None,
    previous_questions: list[str] | None,
    conversation_context: list[dict[str, str]] | None,
    retrieved_examples: list[dict] | None,
) -> str:

    symptoms = associated_symptoms or []
    missing_fields = missing_nlice_fields or []
    previous = previous_questions or []

    return f"""You are a clinician conducting a concise triage intake conversation.

Your task:
Generate ONE natural clinician-style follow-up question for the specified exploration focus.

COMPLAINT
{complaint}

EXPLORATION FOCUS
{focus}: {FOCUS_GUIDANCE.get(focus, FOCUS_GUIDANCE["contextual_followup"])}

CURRENT NLICE STATE
{_format_nlice_state(nlice_state)}

MISSING NLICE FIELDS
{', '.join(missing_fields) if missing_fields else '(None)'}

KNOWN ASSOCIATED SYMPTOMS
{', '.join(symptoms) if symptoms else '(None reported yet)'}

RETRIEVED CLINICIAN EXAMPLES
{_format_examples(retrieved_examples)}

RECENT CONVERSATION
{_format_context(conversation_context)}

PREVIOUSLY ASKED QUESTIONS
{', '.join(previous) if previous else '(None yet)'}

QUESTIONING STRATEGY
- Use retrieved examples to infer what clinicians usually ask next.
- Make the conversation feel like clinical exploration, not a form.
- NLICE should be advanced naturally when possible, but do not sound like a checklist.
- For fever, associated symptom exploration should consider chills, cough, body aches, headache, vomiting, breathing difficulty, rash, and weakness when appropriate.
- For red flags, ask about breathing difficulty, confusion, severe weakness, persistent vomiting, chest pain, fainting, stiff neck, or severe dehydration when appropriate.
- If focus is nlice_blend, ask a contextual question that can fill intensity, chronology, or excitation without sounding generic.

STRICT RULES
- Ask ONE question only.
- Do not diagnose.
- Do not recommend tests or treatment.
- Do not repeat previous questions.
- Do not ask generic form questions like "Rate your symptom from 1 to 10" unless it is clinically framed.
- Keep it concise and patient-friendly.

OUTPUT
Return only the question text.
"""


def _clean_question(
    text: str,
) -> str:

    cleaned = (text or "").strip().split("\n")[0].strip()
    cleaned = re.sub(
        r"^(Q\d+:|Question:|\d+\.)\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned.strip("\"' ")


def _fallback_question(
    complaint: str,
    focus: str,
    nlice_state: dict | None,
) -> str:

    symptom = (
        (nlice_state or {}).get("nature")
        or complaint
        or "your symptom"
    )
    symptom = str(symptom).strip()
    complaint_lower = (complaint or "").lower()

    if "fever" in complaint_lower or symptom.lower() == "fever":
        fallback_map = {
            "associated_symptoms": (
                "I'm sorry you're feeling unwell. Have you noticed chills, cough, body aches, vomiting, breathing trouble, or headache with the fever?"
            ),
            "red_flags": (
                "Are you having any breathing difficulty, confusion, severe weakness, persistent vomiting, or chest pain with the fever?"
            ),
            "nlice_blend": (
                "Have you checked your temperature, and does the fever improve after medication or worsen at certain times?"
            ),
            "contextual_followup": (
                "Have the body aches or headache been getting worse along with the fever?"
            ),
        }
        return fallback_map.get(
            focus,
            fallback_map["associated_symptoms"],
        )

    fallback_map = {
        "associated_symptoms": (
            f"What other symptoms have you noticed along with {symptom}?"
        ),
        "red_flags": (
            f"Are you having any severe weakness, breathing difficulty, chest pain, fainting, or confusion with {symptom}?"
        ),
        "nlice_blend": (
            f"What seems to worsen or relieve {symptom}, and how severe is it at its worst?"
        ),
        "contextual_followup": (
            f"What changes have you noticed since {symptom} started?"
        ),
    }

    return fallback_map.get(
        focus,
        fallback_map["contextual_followup"],
    )


def clinical_exploration_agent(
    complaint: str,
    focus: str,
    nlice_state: dict | None = None,
    associated_symptoms: list[str] | None = None,
    missing_nlice_fields: list[str] | None = None,
    previous_questions: list[str] | None = None,
    conversation_context: list[dict[str, str]] | None = None,
    top_k: int = 4,
) -> ClinicalExplorationResult:

    examples: list[dict] = []
    retrieval_error = None
    retrieval_query = " | ".join(
        part
        for part in [
            complaint,
            focus,
            "associated symptoms red flags clinician follow up",
            " ".join(associated_symptoms or []),
        ]
        if part
    )

    try:
        retrieval_result = retrieve_followup_examples(
            patient_complaint=retrieval_query,
            top_k=top_k,
        )
        if retrieval_result.get("success"):
            examples = retrieval_result.get("examples", [])
        else:
            retrieval_error = retrieval_result.get("error")

    except Exception as exc:
        retrieval_error = str(exc)
        print(f"Clinical exploration retrieval error: {exc}")

    prompt = _build_exploration_prompt(
        complaint=complaint,
        focus=focus,
        nlice_state=nlice_state,
        associated_symptoms=associated_symptoms,
        missing_nlice_fields=missing_nlice_fields,
        previous_questions=previous_questions,
        conversation_context=conversation_context,
        retrieved_examples=examples,
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt],
        )
        question = _clean_question(response.text or "")

        if not question:
            raise ValueError("Empty response from Gemini")

        return {
            "success": True,
            "question": question,
            "focus": focus,
            "source": "retrieved" if examples else "gemini",
            "error": retrieval_error,
            "retrieved_examples": examples,
        }

    except Exception as exc:
        print(f"Clinical exploration generation error: {exc}")
        return {
            "success": False,
            "question": _fallback_question(
                complaint=complaint,
                focus=focus,
                nlice_state=nlice_state,
            ),
            "focus": focus,
            "source": "fallback",
            "error": str(exc),
            "retrieved_examples": [],
        }
