"""
Retrieval-Augmented Follow-Up Question Agent.

This module generates clinician-style follow-up questions while keeping
workflow control outside the LLM. LangGraph decides the missing NLICE field;
this agent only turns that target into a symptom-contextual question.
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


class FollowupQuestionResult(TypedDict, total=False):
    """Result of follow-up question generation."""

    success: bool
    question: str
    reasoning: str | None
    source: str | None
    error: str | None
    retrieved_examples: list[dict] | None


NLICE_FIELDS = (
    "nature",
    "location",
    "intensity",
    "chronology",
    "excitation",
)

MISSING_VALUES = {
    "",
    "unknown",
    "not specified",
    "null",
    "n/a",
}


def _nlice_value_is_missing(
    field: str,
    value,
) -> bool:

    normalized = (
        str(value or "")
        .strip()
        .lower()
    )

    if field == "excitation" and normalized in {
        "none",
        "no",
        "nothing",
        "not really",
    }:
        return False

    return normalized in MISSING_VALUES


def _first_missing_field(
    nlice_state: dict | None,
) -> str:

    nlice = nlice_state or {}

    for field in NLICE_FIELDS:
        if _nlice_value_is_missing(
            field,
            nlice.get(field),
        ):
            return field

    return "nature"


def _retrieval_query(
    complaint: str,
    nlice_state: dict | None,
    target_field: str,
) -> str:
    """
    Add NLICE context to the semantic query so retrieval is about the current
    clinical question, not just the raw complaint phrasing.
    """

    nlice = nlice_state or {}
    context_parts = [
        complaint or "",
        f"missing {target_field}",
    ]

    for field in ("nature", "location", "chronology"):
        value = nlice.get(field)
        if value and not _nlice_value_is_missing(field, value):
            context_parts.append(f"{field}: {value}")

    return " | ".join(
        part for part in context_parts
        if str(part).strip()
    )


def _format_nlice_state(
    nlice_state: dict | None,
) -> str:

    nlice = nlice_state or {}
    lines = []

    for field in NLICE_FIELDS:
        value = nlice.get(field, "")
        status = (
            f"Filled: {value}"
            if not _nlice_value_is_missing(field, value)
            else "Missing"
        )
        lines.append(f"- {field}: {status}")

    return "\n".join(lines)


def _format_retrieved_examples(
    examples: list[dict] | None,
) -> str:

    if not examples:
        return "(No retrieved examples available.)"

    blocks = []

    for index, example in enumerate(examples[:3], 1):
        lines = [
            f"[Example {index}]",
            f"Patient complaint: {example.get('message', '')}",
        ]

        questions = example.get("questions") or []
        if questions:
            lines.append("Clinician follow-up questions:")
            for question in questions[:4]:
                lines.append(f"- {question}")

        ehr = (example.get("ehr") or "").strip()
        if ehr:
            lines.append(f"EHR context: {ehr[:240]}")

        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)


def _format_conversation_context(
    conversation_context: list[dict[str, str]] | None,
) -> str:

    if not conversation_context:
        return "(None yet)"

    lines = []

    for turn in conversation_context[-6:]:
        role = turn.get("role", "message")
        content = turn.get("content", "")
        if content:
            lines.append(f"{role}: {content}")

    return "\n".join(lines) if lines else "(None yet)"


def _target_field_guidance(
    target_field: str,
) -> str:

    guidance = {
        "nature": (
            "Clarify the symptom quality or character in terms that fit "
            "the complaint."
        ),
        "location": (
            "Clarify anatomical location, distribution, radiation, or the "
            "most affected area."
        ),
        "intensity": (
            "Ask for severity using a 1 to 10 scale, grounded in the symptom."
        ),
        "chronology": (
            "Clarify onset, duration, progression, frequency, or timing pattern."
        ),
        "excitation": (
            "Clarify triggers, relieving factors, worsening factors, time-of-day "
            "variation, exertional pattern, posture relation, food relation, or "
            "response to medication when clinically relevant."
        ),
    }

    return guidance.get(
        target_field,
        "Ask for the missing clinical detail.",
    )


def _build_retrieval_prompt(
    patient_complaint: str,
    target_field: str,
    nlice_state: dict | None = None,
    associated_symptoms: list[str] | None = None,
    previously_asked_questions: list[str] | None = None,
    conversation_context: list[dict[str, str]] | None = None,
    retrieved_examples: list[dict] | None = None,
) -> str:
    """
    Build a prompt that binds Gemini to the deterministic NLICE target while
    giving it retrieved clinician examples for contextual strategy.
    """

    previous_questions = previously_asked_questions or []
    symptoms = associated_symptoms or []

    return f"""You are a clinician performing structured clinical history-taking.

Your ONLY task:
Generate ONE clinician-style follow-up question targeting the specified missing NLICE field.
Do not diagnose, prescribe, recommend tests, or suggest new treatment.

PATIENT COMPLAINT
{patient_complaint}

TARGET NLICE FIELD
{target_field}

TARGET FIELD STRATEGY
{_target_field_guidance(target_field)}

CURRENT NLICE STATE
{_format_nlice_state(nlice_state)}

KNOWN ASSOCIATED SYMPTOMS
{', '.join(symptoms) if symptoms else '(None reported yet)'}

RETRIEVED CLINICIAN EXAMPLES FROM SIMILAR CASES
{_format_retrieved_examples(retrieved_examples)}

PREVIOUSLY ASKED QUESTIONS
{', '.join(previous_questions) if previous_questions else '(None yet)'}

RECENT CONVERSATION CONTEXT
{_format_conversation_context(conversation_context)}

INSTRUCTIONS
1. Generate ONE question only.
2. The question must target the TARGET NLICE FIELD: {target_field}.
3. Keep the question symptom-contextual and medically realistic.
4. Use retrieved examples for clinical questioning strategy, not just wording.
5. Ask about the patient's actual complaint instead of using generic placeholders like "it" when the symptom is known.
6. Avoid repeating any previous question.
7. Use known associated symptoms to make the question clinically continuous.
8. Prefer concrete clinical anchors such as timing, medication response, triggers, chills, sweating, exertion, posture, food, or progression when relevant.
9. If the complaint is fever and the target is excitation, ask about time-of-day worsening, medication response, chills/sweating, or triggers.

STRICT RULES
- Do NOT diagnose diseases.
- Do NOT recommend starting medicines or treatments.
- Do NOT suggest diagnostic tests.
- Do NOT ask more than one question.
- Do NOT ask a generic NLICE template such as "Does anything make it better or worse?" unless no symptom context exists.
- Do NOT change the target field.

OUTPUT FORMAT
Return ONLY the question text. No numbering, no explanation, no prefix.

Example valid outputs:
Does the fever worsen at night or improve after medication?
On a scale from 1 to 10, how severe is the chest pain at its worst?
Where in your abdomen is the cramping strongest?
"""


def _clean_question(
    text: str,
) -> str:

    cleaned = (text or "").strip()
    cleaned = cleaned.split("\n")[0].strip()
    cleaned = re.sub(
        r"^(Q\d+:|Question:|\d+\.)\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    cleaned = cleaned.strip("\"' ")

    return cleaned


def _is_generic_question(
    question: str,
) -> bool:

    normalized = (
        question.lower()
        .strip()
        .rstrip("?")
    )

    return normalized in {
        "does anything make it better or worse",
        "what makes it better or worse",
        "can you tell me more",
        "tell me more about this symptom",
    }


def followup_question_agent(
    complaint: str,
    nlice_state: dict | None = None,
    target_field: str | None = None,
    associated_symptoms: list[str] | None = None,
    previous_questions: list[str] | None = None,
    conversation_context: list[dict[str, str]] | None = None,
    top_k: int = 3,
) -> FollowupQuestionResult:
    """
    Generate a contextual follow-up question for one deterministic NLICE field.
    """

    selected_field = target_field or _first_missing_field(
        nlice_state
    )

    examples: list[dict] = []
    retrieval_error = None

    try:
        retrieval_result = retrieve_followup_examples(
            patient_complaint=_retrieval_query(
                complaint,
                nlice_state,
                selected_field,
            ),
            top_k=top_k,
        )

        if retrieval_result.get("success"):
            examples = retrieval_result.get("examples", [])
        else:
            retrieval_error = retrieval_result.get("error")

    except Exception as exc:
        retrieval_error = str(exc)
        print(f"Retrieval error: {exc}")

    prompt = _build_retrieval_prompt(
        patient_complaint=complaint,
        target_field=selected_field,
        nlice_state=nlice_state,
        associated_symptoms=associated_symptoms,
        previously_asked_questions=previous_questions,
        conversation_context=conversation_context,
        retrieved_examples=examples,
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt],
        )

        question = _clean_question(
            response.text or ""
        )

        if not question:
            raise ValueError("Empty response from Gemini")

        if _is_generic_question(question) and complaint:
            raise ValueError(
                "Gemini returned a generic NLICE template"
            )

        return {
            "success": True,
            "question": question,
            "reasoning": (
                f"Generated for NLICE field: {selected_field}"
            ),
            "source": "retrieved" if examples else "gemini",
            "error": retrieval_error,
            "retrieved_examples": examples,
        }

    except Exception as exc:
        print(f"Gemini generation error: {exc}")
        return _fallback_question(
            complaint=complaint,
            nlice_state=nlice_state,
            target_field=selected_field,
            error_msg=str(exc),
        )


def _fallback_question(
    complaint: str = "",
    nlice_state: dict | None = None,
    target_field: str | None = None,
    error_msg: str | None = None,
) -> FollowupQuestionResult:
    """
    Safe deterministic fallback used only when retrieval/Gemini fails.
    """

    selected_field = target_field or _first_missing_field(
        nlice_state
    )
    symptom = (
        (nlice_state or {}).get("nature")
        or complaint
        or "the symptom"
    )
    symptom = str(symptom).strip()

    fallback_map = {
        "nature": (
            "What does the symptom feel like?"
        ),
        "location": (
            f"Where exactly do you feel {symptom}?"
        ),
        "intensity": (
            f"On a scale from 1 to 10, how severe is {symptom}?"
        ),
        "chronology": (
            f"When did {symptom} start?"
        ),
        "excitation": (
            f"Does {symptom} worsen at certain times or improve after anything?"
        ),
    }

    return {
        "success": False,
        "question": fallback_map.get(
            selected_field,
            "Can you tell me more about this symptom?",
        ),
        "reasoning": (
            f"Fallback for NLICE field: {selected_field}"
        ),
        "source": "fallback",
        "error": error_msg,
        "retrieved_examples": [],
    }


if __name__ == "__main__":
    result = followup_question_agent(
        complaint="fever for 3 days",
        nlice_state={
            "nature": "fever",
            "location": "Systemic/General",
            "intensity": "7",
            "chronology": "3 days",
            "excitation": "",
        },
        target_field="excitation",
        previous_questions=[
            "How severe is the fever on a scale from 1 to 10?",
        ],
    )
    print(result["question"])
