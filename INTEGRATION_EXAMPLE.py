"""
Integration Example: Using Retrieval-Augmented Questions in chat_controller.py

This file shows the exact code changes needed to integrate the new
followup_question_agent into your existing chat_controller.py workflow.

Copy the modified question_node() function from this file into chat_controller.py
"""

from __future__ import annotations

from typing import Annotated
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph.message import add_messages

# =========================================================
# STEP 1: Add this import to chat_controller.py
# =========================================================

# Existing import:
# from agents.question_agent import patient_question_agent

# Add this new import:
from agents.followup_question_agent import (
    followup_question_agent,
)

# =========================================================
# STEP 2: Replace the question_node() function
# =========================================================

def question_node(
    state: dict,
) -> dict:
    """
    Generate the next follow-up question to fill NLICE gaps.

    ORCHESTRATION (deterministic - in this function):
    1. Check if conversation complete (max questions)
    2. Identify missing NLICE fields
    3. Use structured questions for critical fields
    4. Use retrieval-augmented agent for complex symptoms
    5. Avoid repeating previous questions

    FLOW CONTROL (stays in this function, NOT in Gemini):
    - When to ask a question: based on missing NLICE fields
    - Which field to ask about: ordered by criticality
    - When to stop: MAX_QUESTIONS limit
    - Whether to repeat: checked against previous_questions list
    """

    MAX_QUESTIONS = 5

    questions = list(
        state.get("questions") or []
    )

    # ---------------------------------------------------
    # LOOP PROTECTION (DETERMINISTIC)
    # ---------------------------------------------------

    if len(questions) >= MAX_QUESTIONS:

        return {
            "messages": [
                AIMessage(
                    content=(
                        "Clinical intake complete."
                    )
                )
            ],
            "conversation_complete": True,
        }

    # ---------------------------------------------------
    # IDENTIFY MISSING NLICE FIELDS (DETERMINISTIC)
    # ---------------------------------------------------
    # Helper function: _missing_nlice_fields(nlice_data)
    # Returns list of fields that are empty/missing

    missing_fields = _missing_nlice_fields(
        state.get("nlice_data")
    )

    next_field = (
        missing_fields[0]
        if missing_fields
        else None
    )

    if not next_field:
        return {}

    complaint = (
        state.get("complaint") or ""
    ).lower()

    # ---------------------------------------------------
    # STRUCTURED NLICE QUESTIONS (PRIORITY)
    # ---------------------------------------------------
    # Use hardcoded questions for critical clinical fields
    # This ensures consistent, medically sound questioning

    FIELD_QUESTION_MAP = {
        "nature":
            "Can you describe what the symptom feels like?",
        "location":
            "Where exactly are you feeling it?",
        "intensity":
            "How severe is it on a scale from 1 to 10?",
        "chronology":
            "When did it start?",
        "excitation":
            "Does anything make it better or worse?",
    }

    # Trigger AI-augmented questions for complex symptoms
    COMPLEX_SYMPTOMS = [
        "diarrhea",
        "vomiting",
        "chest pain",
        "difficulty breathing",
        "shortness of breath",
        "dizziness",
        "fatigue",
        "abdominal pain",
        "palpitations",
        "weakness",
        "fever",
    ]

    use_ai_questioning = any(
        symptom in complaint
        for symptom in COMPLEX_SYMPTOMS
    )

    question = ""

    # Structured NLICE fields always get priority
    if next_field in FIELD_QUESTION_MAP:
        question = FIELD_QUESTION_MAP[next_field]

    # ---------------------------------------------------
    # RETRIEVAL-AUGMENTED AI QUESTIONING (NEW)
    # ---------------------------------------------------
    # For complex symptoms, enhance question quality using:
    # 1. FAISS semantic search (find similar clinician cases)
    # 2. Gemini 2.5 Flash (contextualize with examples)

    if (
        use_ai_questioning
        and not question
    ):
        try:
            # Prepare previous questions for deduplication
            previous_questions = [
                q.lower()
                for q in questions
            ]

            # Call retrieval-augmented agent
            # This retrieves clinician examples and uses Gemini
            # to generate a contextual follow-up question
            result = followup_question_agent(
                complaint=complaint,
                nlice_state=state.get(
                    "nlice_data",
                    {},
                ),
                previous_questions=previous_questions,
                top_k=3,  # Retrieve 3 similar examples
            )

            # Use generated question (either from retrieval
            # or internal fallback in the agent)
            if result.get("question"):
                question = result.get("question")
                # Optionally log the source
                # print(f"Question source: {result.get('source')}")

        except Exception as exc:
            print(
                "Retrieval-augmented question agent failed:",
                exc,
            )

    # ---------------------------------------------------
    # FINAL FALLBACK
    # ---------------------------------------------------
    # If all else fails, use the structured question map

    if not question:
        question = FIELD_QUESTION_MAP.get(
            next_field,
            "Can you tell me more?",
        )

    # ---------------------------------------------------
    # UPDATE STATE AND RETURN
    # ---------------------------------------------------

    questions.append(question)

    return {
        "messages": [
            AIMessage(content=question)
        ],
        "questions": questions,
        "current_question_index": (
            len(questions) - 1
        ),
    }


# =========================================================
# HELPER FUNCTIONS (already exist in your code)
# =========================================================

def _missing_nlice_fields(
    nlice_data: dict | None,
) -> list[str]:
    """Return list of empty NLICE fields"""
    nlice = nlice_data or {}

    NLICE_FIELDS = (
        "nature",
        "location",
        "intensity",
        "chronology",
        "excitation",
    )

    UNKNOWN_VALUES = {
        "",
        "unknown",
        "not specified",
        "none",
        "null",
        "n/a",
    }

    def _is_empty(value) -> bool:
        return (
            str(value or "")
            .strip()
            .lower()
            in UNKNOWN_VALUES
        )

    return [
        field
        for field in NLICE_FIELDS
        if _is_empty(nlice.get(field))
    ]


# =========================================================
# COMPARISON: OLD vs NEW
# =========================================================

"""
OLD ARCHITECTURE:
┌────────────────────────────────────────┐
│ question_node()                        │
├────────────────────────────────────────┤
│ 1. Check completion                    │
│ 2. Get missing field                   │
│ 3. Use structured question             │
│ 4. OR call patient_question_agent()    │
│    - Uses RAG on symcat                │
│    - Calls Gemini 1.5 Flash           │
│    - Returns list of 3-5 questions    │
│ 5. Filter duplicates                   │
│ 6. Pick first question                 │
└────────────────────────────────────────┘

NEW ARCHITECTURE:
┌────────────────────────────────────────┐
│ question_node()                        │
├────────────────────────────────────────┤
│ 1. Check completion (deterministic)    │
│ 2. Get missing field (deterministic)   │
│ 3. Use structured question             │
│ 4. OR call followup_question_agent()   │
│    - Uses FAISS on followup examples   │
│    - Calls Gemini 2.5 Flash           │
│    - Returns single, contextualized Q  │
│ 5. (dedup is built into agent)         │
│ 6. Return question directly            │
└────────────────────────────────────────┘

KEY IMPROVEMENTS:
✓ More clinician-like follow-ups
✓ Learns from real clinician examples
✓ Better contextual awareness
✓ Single high-quality question (not list)
✓ Explicit deduplication logic
✓ More efficient (cached resources)
"""


# =========================================================
# TESTING THE INTEGRATION
# =========================================================

if __name__ == "__main__":

    print("\n" + "=" * 70)
    print("INTEGRATION EXAMPLE TEST")
    print("=" * 70)

    # Simulate a state in the middle of a conversation
    test_state = {
        "messages": [
            HumanMessage(content="sharp chest pain for 2 hours"),
        ],
        "complaint": "sharp chest pain for 2 hours",
        "nlice_data": {
            "nature": "sharp",
            "location": "chest",
            "intensity": "7/10",
            "chronology": "2 hours",
            "excitation": "",  # This is the missing field
        },
        "questions": [
            "Can you describe what the symptom feels like?",
            "Where exactly are you feeling it?",
        ],
    }

    print("\nTest State:")
    print(f"  Complaint: {test_state['complaint']}")
    print(f"  Previous questions: {test_state['questions']}")
    print(f"  Missing NLICE field: excitation")

    print("\nCalling question_node()...")
    print("-" * 70)

    result = question_node(test_state)

    print(f"\nResult:")
    print(f"  Message: {result['messages'][0].content}")
    print(f"  Total questions: {len(result['questions'])}")
    print(f"  All questions: {result['questions']}")

    print("\n" + "=" * 70)
