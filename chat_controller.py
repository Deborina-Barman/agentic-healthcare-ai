# Updated `chat_controller.py`

from __future__ import annotations

from dataclasses import fields
import json
import os
import re
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from google import genai
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
)
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from agents.clinical_context_agent import (
    clinical_context_agent,
)
from agents.clinical_exploration_agent import (
    clinical_exploration_agent,
)
from agents.followup_question_agent  import (
    followup_question_agent,
)
from agents.reader_agent import (
    vision_reader_agent,
)
from agents.summary_agent import summary_agent
from agents.urgency_classifier_agent import (
    urgency_classifier_agent,
)
from clinical_workflows import (
    get_workflow,
    workflow_key_for_complaint,
)


# =========================================================
# CONSTANTS
# =========================================================

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


# =========================================================
# STATE
# =========================================================

class ClinicalState(TypedDict, total=False):

    messages: Annotated[
        list[BaseMessage],
        add_messages,
    ]

    age_gender: str | None
    complaint: str | None
    duration: str | None
    medications: str | None

    nlice_data: dict
    nlice: dict

    urgency: str | None
    urgency_score: int | None

    step: str
    case_type: str | None

    vision_output: dict | None

    questions: list[str]
    exploration_questions: list[str]
    current_question_index: int

    patient_answers: dict
    associated_symptoms: list[str]
    red_flags_screened: bool

    allergies: str | None
    past_history: str | None

    clinical_context: str | None
    summary: str | None
    normalized_summary: str | None
    recommendations: list[str]
    validation_warnings: list[str]

    # NEW
    turn_count: int
    conversation_complete: bool
    concept_memory: dict
    uncertainty_count: int
    workflow_key: str | None
    clinical_fields: dict


# =========================================================
# GEMINI CLIENT
# =========================================================

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)


# =========================================================
# HELPERS
# =========================================================


def _empty_nlice() -> dict:

    return {
        "nature": "",
        "location": "",
        "intensity": "",
        "chronology": "",
        "excitation": "",
    }



def _is_empty(value) -> bool:

    return (
        str(value or "")
        .strip()
        .lower()
        in UNKNOWN_VALUES
    )


def _is_missing_nlice_value(
    field: str,
    value,
) -> bool:
    """
    Field-aware missing check.

    "none" is clinically meaningful for excitation because it can mean
    no trigger, reliever, or worsening factor was identified.
    """

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
        "no clear trigger",
        "no known trigger",
    }:
        return False

    return normalized in UNKNOWN_VALUES



def _missing_nlice_fields(
    nlice_data: dict | None,
) -> list[str]:

    nlice = nlice_data or {}

    return [
        field
        for field in NLICE_FIELDS
        if _is_missing_nlice_value(
            field,
            nlice.get(field),
        )
    ]



def _latest_user_message(
    messages: list[BaseMessage] | None,
) -> str:

    for message in reversed(messages or []):

        if getattr(message, "type", None) == "human":
            return str(message.content)

    return ""


def _latest_ai_message(
    messages: list[BaseMessage] | None,
) -> str:

    for message in reversed(messages or []):

        if getattr(message, "type", None) == "ai":
            return str(message.content)

    return ""


def _compact_conversation_context(
    messages: list[BaseMessage] | None,
    limit: int = 6,
) -> list[dict[str, str]]:

    recent_messages = list(messages or [])[-limit:]
    context = []

    for message in recent_messages:
        role = getattr(message, "type", "")
        if role == "human":
            speaker = "patient"
        elif role == "ai":
            speaker = "assistant"
        else:
            speaker = role or "message"

        context.append(
            {
                "role": speaker,
                "content": str(
                    getattr(message, "content", "")
                ),
            }
        )

    return context


ASSOCIATED_SYMPTOM_TERMS = (
    "chills",
    "cough",
    "vomiting",
    "nausea",
    "body ache",
    "body aches",
    "body pain",
    "headache",
    "breathing difficulty",
    "difficulty breathing",
    "shortness of breath",
    "rash",
    "weakness",
    "fatigue",
    "sore throat",
    "runny nose",
    "diarrhea",
    "dizziness",
    "chest pain",
    "sweating",
)

SYMPTOM_CANONICAL_NAMES = {
    "body ache": "body aches",
    "body pain": "body aches",
    "difficulty breathing": "breathing difficulty",
    "shortness of breath": "breathing difficulty",
    "trouble breathing": "breathing difficulty",
    "chest pressure": "chest pain",
    "vomit": "vomiting",
    "persistent vomiting": "vomiting",
    "severe weakness": "weakness",
}

SYMPTOM_FIELD_NAMES = {
    "cough": "cough",
    "breathing difficulty": "breathing_difficulty",
    "weakness": "weakness",
    "severe weakness": "weakness",
    "vomiting": "vomiting",
    "diarrhea": "diarrhea",
    "rash": "rash",
    "confusion": "confusion",
    "chest pain": "chest_pain",
    "chills": "chills",
    "body aches": "body_aches",
    "sweating": "sweating",
    "dizziness": "dizziness",
    "fainting": "fainting",
}

SYMPTOM_ALIASES = tuple(
    sorted(
        {
            *ASSOCIATED_SYMPTOM_TERMS,
            *SYMPTOM_CANONICAL_NAMES,
            "confusion",
            "severe weakness",
            "persistent vomiting",
            "trouble breathing",
            "chest pressure",
            "vomit",
            "fainting",
        },
        key=len,
        reverse=True,
    )
)

RED_FLAG_TERMS = (
    "breathing difficulty",
    "difficulty breathing",
    "shortness of breath",
    "confusion",
    "chest pain",
    "fainting",
    "persistent vomiting",
    "severe weakness",
    "stiff neck",
    "dehydration",
)


CONCEPT_PATTERNS = {
    "pain_quality": (
        "feel like",
        "sharp",
        "pressure",
        "tightness",
        "squeezing",
        "burning",
        "heavy",
        "dull",
        "stabbing",
        "aching",
        "nature",
        "quality",
    ),
    "breathing": (
        "breath",
        "breathing",
        "shortness of breath",
        "difficulty breathing",
    ),
    "severity": (
        "severity",
        "severe",
        "scale",
        "rate",
        "rating",
        "out of 10",
        "pain scale",
    ),
    "medication": (
        "medicine",
        "medication",
        "tablet",
        "paracetamol",
        "acetaminophen",
        "ibuprofen",
        "relief",
        "helped",
    ),
    "hydration": (
        "hydration",
        "dehydration",
        "fluid",
        "urine",
        "thirst",
        "vomiting",
        "diarrhea",
    ),
    "duration": (
        "when did",
        "how long",
        "started",
        "since",
        "duration",
    ),
    "location": (
        "where",
        "location",
        "which part",
        "chest",
        "head",
        "stomach",
        "abdomen",
        "back",
        "arm",
        "leg",
    ),
    "associated_symptoms": (
        "other symptoms",
        "along with",
        "associated",
        "vomiting",
        "cough",
        "headache",
        "sweating",
        "nausea",
        "diarrhea",
        "weakness",
        "fatigue",
        "chills",
        "body aches",
    ),
    "vomiting": (
        "vomit",
        "vomiting",
        "nausea",
    ),
    "travel": (
        "travel",
        "trip",
        "outside",
        "mosquito",
        "dengue",
        "malaria",
    ),
    "exposure": (
        "exposure",
        "contact",
        "infection",
        "sick",
        "recent infection",
    ),
    "cardiac_quality": (
        "pressure",
        "squeezing",
        "burning",
        "sharp",
    ),
    "radiation": (
        "left arm",
        "jaw",
        "back",
        "shoulder",
        "spread",
    ),
    "exertion": (
        "walking",
        "exertion",
        "deep breathing",
    ),
    "neurologic": (
        "confusion",
        "fainting",
        "neck stiffness",
        "vision",
        "one side",
    ),
    "headache_severity": (
        "worst headache",
        "suddenly",
        "sudden",
    ),
    "gastrointestinal": (
        "abdominal",
        "stomach",
        "vomiting",
        "diarrhea",
        "blood in stool",
    ),
    "red_flags": (
        "confusion",
        "fainting",
        "chest pain",
        "severe weakness",
        "persistent vomiting",
        "stiff neck",
    ),
}

CONCEPT_FOR_TARGET = {
    "nature": "pain_quality",
    "location": "location",
    "intensity": "severity",
    "chronology": "duration",
    "excitation": "medication",
    "associated_symptoms": "associated_symptoms",
    "red_flags": "red_flags",
    "contextual_followup": "associated_symptoms",
    "nlice_blend": "medication",
}

UNCERTAINTY_TERMS = (
    "don't know",
    "dont know",
    "do not know",
    "not sure",
    "maybe",
    "unsure",
    "can't tell",
    "cannot tell",
    "no idea",
)


def _extract_associated_symptoms(
    user_text: str,
    existing_symptoms: list[str] | None = None,
) -> list[str]:

    polarity = _symptom_polarity_from_text(user_text)
    symptoms = [
        symptom
        for symptom in list(existing_symptoms or [])
        if polarity.get(_canonical_symptom_name(symptom), True)
    ]
    symptom_set = {
        symptom.lower()
        for symptom in symptoms
    }

    for symptom, is_positive in polarity.items():
        if not is_positive:
            continue
        if symptom not in symptom_set:
            symptoms.append(symptom)
            symptom_set.add(symptom)

    return symptoms


def _has_red_flag(
    text: str,
) -> bool:

    polarity = _symptom_polarity_from_text(text)
    if any(
        polarity.get(_canonical_symptom_name(term)) is True
        for term in RED_FLAG_TERMS
    ):
        return True

    if any(
        polarity.get(_canonical_symptom_name(term)) is False
        for term in RED_FLAG_TERMS
    ):
        return False

    return False


def _text_has_concept(
    text: str,
    concept: str,
) -> bool:

    normalized = (text or "").lower()
    return any(
        pattern in normalized
        for pattern in CONCEPT_PATTERNS.get(concept, ())
    )


def _concepts_from_text(
    text: str,
) -> set[str]:

    return {
        concept
        for concept in CONCEPT_PATTERNS
        if _text_has_concept(text, concept)
    }


def _is_uncertain_reply(
    text: str,
) -> bool:

    normalized = (text or "").lower()
    return any(
        term in normalized
        for term in UNCERTAINTY_TERMS
    )


def _update_concept_memory(
    state: ClinicalState,
    user_text: str,
    latest_ai_text: str,
) -> dict:

    memory = dict(
        state.get("concept_memory") or {}
    )
    explored = set(
        memory.get("explored", [])
    )
    uncertain = set(
        memory.get("uncertain", [])
    )

    concepts = (
        _concepts_from_text(latest_ai_text)
        | _concepts_from_text(user_text)
    )

    target = _conversation_target_field(
        state.get("nlice_data") or _empty_nlice(),
        state.get("messages"),
    )
    latest_ai_concepts = _concepts_from_text(latest_ai_text)

    if (
        target in CONCEPT_FOR_TARGET
        and latest_ai_concepts
    ):
        concepts.add(CONCEPT_FOR_TARGET[target])

    for concept in concepts:
        explored.add(concept)

    if _is_uncertain_reply(user_text):
        uncertain.update(concepts or {"general"})

    memory["explored"] = sorted(explored)
    memory["uncertain"] = sorted(uncertain)
    return memory


def _canonical_symptom_name(
    symptom: str,
) -> str:

    normalized = (
        symptom or ""
    ).strip().lower()

    return SYMPTOM_CANONICAL_NAMES.get(normalized, normalized)


def _is_negated_mention(
    text: str,
    start: int,
) -> bool:

    prefix = text[max(0, start - 80):start]
    return bool(
        re.search(
            r"(?:\bno\b|\bnone\b|\bdenies?\b|\bdeny\b|\bwithout\b|"
            r"\bnot\s+(?:having|experiencing|feeling)?\b|"
            r"\bno\s+signs?\s+of\b)\s+[\w\s,/-]{0,60}$",
            prefix,
        )
    )


def _symptom_polarity_from_text(
    user_text: str,
) -> dict[str, bool]:

    text = re.sub(
        r"\s+",
        " ",
        (user_text or "").lower(),
    )
    polarity: dict[str, bool] = {}

    for alias in SYMPTOM_ALIASES:
        canonical = _canonical_symptom_name(alias)
        pattern = rf"\b{re.escape(alias)}\b"

        for match in re.finditer(pattern, text):
            is_positive = not _is_negated_mention(
                text,
                match.start(),
            )
            polarity[canonical] = is_positive

    if re.search(r"\bno\s+red\s+flags?\b|\bdenies?\s+red\s+flags?\b", text):
        for symptom in (
            "breathing difficulty",
            "confusion",
            "chest pain",
            "fainting",
            "vomiting",
            "severe weakness",
            "stiff neck",
            "rash",
        ):
            polarity[_canonical_symptom_name(symptom)] = False

    return polarity


def _medication_taken_from_text(
    user_text: str,
) -> bool | None:

    text = re.sub(
        r"\s+",
        " ",
        (user_text or "").lower(),
    )
    medication_pattern = (
        r"\b(paracetamol|acetaminophen|ibuprofen|aspirin|medicine|"
        r"medication|tablet|tablets)\b"
    )

    if re.search(
        rf"\b(no|not|never|without)\b[\w\s,/-]{{0,50}}"
        rf"\b(taken|took|take|had|used|using)\b[\w\s,/-]{{0,50}}"
        rf"{medication_pattern}",
        text,
    ) or re.search(
        rf"\b(taken|took|take|had|used|using)\b[\w\s,/-]{{0,50}}"
        rf"\b(no|not|never)\b[\w\s,/-]{{0,50}}{medication_pattern}",
        text,
    ):
        return False

    if re.search(
        rf"\b(taken|took|take|had|used|using)\b[\w\s,/-]{{0,50}}"
        rf"{medication_pattern}",
        text,
    ) or re.search(
        rf"\b(yes|yeah|yep)\b[\w\s,/-]{{0,30}}{medication_pattern}",
        text,
    ):
        return True

    return None


def _question_concept(
    question: str,
    target: str | None = None,
) -> str | None:

    if target in CONCEPT_FOR_TARGET:
        return CONCEPT_FOR_TARGET[target]

    concepts = _concepts_from_text(question)
    return sorted(concepts)[0] if concepts else None


def _token_set(
    text: str,
) -> set[str]:

    stopwords = {
        "a",
        "an",
        "are",
        "can",
        "could",
        "do",
        "does",
        "did",
        "for",
        "from",
        "have",
        "having",
        "how",
        "is",
        "it",
        "of",
        "on",
        "or",
        "the",
        "this",
        "to",
        "what",
        "when",
        "where",
        "with",
        "you",
        "your",
    }

    return {
        token
        for token in re.findall(
            r"[a-z0-9]+",
            (text or "").lower(),
        )
        if token not in stopwords and len(token) > 2
    }


def _semantic_similarity(
    left: str,
    right: str,
) -> float:

    left_tokens = _token_set(left)
    right_tokens = _token_set(right)

    if not left_tokens or not right_tokens:
        return 0.0

    overlap = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    lexical = overlap / union

    left_concepts = _concepts_from_text(left)
    right_concepts = _concepts_from_text(right)
    concept_overlap = 0.35 if left_concepts & right_concepts else 0.0

    return min(1.0, lexical + concept_overlap)


def _is_semantically_redundant_question(
    candidate_question: str,
    previous_questions: list[str],
    concept_memory: dict | None,
    target: str | None = None,
) -> bool:

    concept = _question_concept(
        candidate_question,
        target,
    )
    explored = set(
        (concept_memory or {}).get("explored", [])
    )

    if concept and concept in explored:
        return True

    return any(
        _semantic_similarity(candidate_question, previous) >= 0.55
        for previous in previous_questions
    )


def _uncertainty_followup(
    concept: str | None,
) -> str:

    options = {
        "pain_quality": (
            "That's okay. Would you say it feels more sharp, squeezing, burning, heavy, or tight?"
        ),
        "breathing": (
            "That's okay. Are you able to speak normally, or do you feel short of breath even at rest?"
        ),
        "severity": (
            "That's okay. Would you call it mild, moderate, severe, or the worst you have felt?"
        ),
        "medication": (
            "That's okay. Have you taken any medicine for this, even if you are not sure of the name?"
        ),
        "hydration": (
            "That's okay. Are you able to keep fluids down and urinating normally?"
        ),
    }

    return options.get(
        concept or "",
        "That's okay. What detail feels easiest to describe right now?",
    )


def _next_unexplored_question(
    state: ClinicalState,
    target: str | None,
) -> str:

    complaint = (
        state.get("complaint") or "the symptom"
    )
    memory = state.get("concept_memory") or {}
    explored = set(memory.get("explored", []))

    concept_questions = [
        (
            "breathing",
            "Are you having any shortness of breath or difficulty breathing?",
        ),
        (
            "severity",
            "How severe is it on a scale from 1 to 10?",
        ),
        (
            "duration",
            f"When did {complaint} start?",
        ),
        (
            "location",
            "Where exactly are you feeling it?",
        ),
        (
            "medication",
            "Have you taken any medication for it, and did it help?",
        ),
        (
            "associated_symptoms",
            "Have you noticed any other symptoms with it?",
        ),
    ]

    preferred = CONCEPT_FOR_TARGET.get(str(target))
    if preferred and preferred not in explored:
        for concept, question in concept_questions:
            if concept == preferred:
                return question

    for concept, question in concept_questions:
        if concept not in explored:
            return question

    return "Is there anything new or worsening since we started talking?"


def _priority_followup_questions(
    state: ClinicalState,
) -> list[tuple[str, str]]:

    complaint = str(state.get("complaint") or "").lower()
    symptoms = " ".join(state.get("associated_symptoms") or []).lower()
    clinical_fields = state.get("clinical_fields") or {}
    text = f"{complaint} {symptoms}"
    questions: list[tuple[str, str]] = []

    if _has_high_fever(state):
        questions.extend(
            [
                ("medication", "Have you taken any fever medicine such as paracetamol or ibuprofen, and did the temperature come down?"),
                ("hydration", "Are you able to drink fluids and urinate normally?"),
                ("associated_symptoms", "Are you having chills, body aches, sweating, or severe weakness with the fever?"),
                ("vomiting", "Any vomiting or diarrhea since the fever started?"),
                ("travel", "Any recent travel, mosquito exposure, or time spent in an area with dengue or malaria risk?"),
                ("exposure", "Has anyone around you had a recent fever, cough, flu, COVID, or other infection?"),
            ]
        )

    if (
        clinical_fields.get("chest_pain") is True
        and clinical_fields.get("breathing_difficulty") is True
    ):
        questions.extend(
            [
                ("cardiac_red_flags", "With chest pain and breathing difficulty, do you also have sweating, fainting, pain spreading to the arm or jaw, or severe weakness?"),
                ("exertion", "Did the chest pain or breathing difficulty start with exertion or does it worsen when you walk?"),
            ]
        )

    if "chest pain" in text or clinical_fields.get("chest_pain") is True:
        questions.extend(
            [
                ("cardiac_quality", "Is the chest pain pressure-like, squeezing, burning, or sharp?"),
                ("radiation", "Does the pain spread to your left arm, jaw, back, or shoulder?"),
                ("exertion", "Does it worsen with walking, exertion, or deep breathing?"),
            ]
        )

    if "headache" in text:
        questions.extend(
            [
                ("neurologic", "Any confusion, fainting, neck stiffness, weakness on one side, or vision changes?"),
                ("headache_severity", "Is this the worst headache you have had or did it start suddenly?"),
            ]
        )

    if (
        clinical_fields.get("cough") is True
        or clinical_fields.get("breathing_difficulty") is True
    ):
        questions.extend(
            [
                ("respiratory", "Are you wheezing, coughing up phlegm, or getting short of breath while speaking or walking?"),
            ]
        )

    if clinical_fields.get("weakness") is True:
        questions.extend(
            [
                ("systemic", "Is the weakness mild, or is it severe enough that you cannot stand, walk, or do usual activities?"),
            ]
        )

    if re.search(r"abdominal|stomach|belly", text):
        questions.extend(
            [
                ("gastrointestinal", "Where is the abdominal pain, and is there vomiting, diarrhea, or blood in stool?"),
                ("hydration", "Are you able to keep fluids down and urinating normally?"),
            ]
        )

    return questions


def _priority_followup_question(
    state: ClinicalState,
) -> tuple[str, str] | None:

    asked_text = " ".join(state.get("questions") or []).lower()
    explored = set((state.get("concept_memory") or {}).get("explored", []))

    for concept, question in _priority_followup_questions(state):
        if concept in explored:
            continue
        if _text_has_concept(asked_text, concept) or concept in asked_text:
            continue
        return concept, question

    return None


def _priority_followups_complete(
    state: ClinicalState,
) -> bool:

    return _priority_followup_question(state) is None


def _canonical_symptom(
    symptom: str,
) -> str:

    return _canonical_symptom_name(symptom)


def _normalize_symptom_list(
    symptoms: list[str] | None,
) -> list[str]:

    seen = set()
    normalized_symptoms = []

    for symptom in symptoms or []:
        canonical = _canonical_symptom(symptom)
        if canonical and canonical not in seen:
            seen.add(canonical)
            normalized_symptoms.append(canonical)

    return normalized_symptoms


def _filter_symptoms_by_clinical_fields(
    symptoms: list[str] | None,
    clinical_fields: dict | None,
) -> list[str]:

    negative_symptoms = set(
        _negative_findings_from_fields(
            {
                "clinical_fields": clinical_fields or {},
            }
        )
    )

    return [
        symptom
        for symptom in _normalize_symptom_list(symptoms)
        if symptom not in negative_symptoms
    ]


def _clean_complaint_text(
    complaint: str | None,
    nlice: dict | None = None,
) -> str:

    text = (complaint or "").strip().lower()
    nlice = nlice or {}

    text = re.sub(
        r"^(i am having|i'm having|im having|i am|i'm|im|i have|having)\s+",
        "",
        text,
    )
    text = re.sub(
        r"\b(for|since)\s+\d+\s*(hours?|days?|weeks?)\b",
        "",
        text,
    )
    text = re.sub(r"\s+", " ", text).strip(" .")

    if not text:
        text = str(nlice.get("nature") or "").strip().lower()

    if "chest" in text and "pain" in text:
        return "chest pain"
    if "fever" in text:
        return "fever"
    if "cough" in text:
        return "cough"
    if "vomit" in text:
        return "vomiting"

    return text or "symptoms"


def _normalized_duration(
    state: ClinicalState,
) -> str:

    nlice = state.get("nlice_data") or {}
    raw = (
        state.get("duration")
        or nlice.get("chronology")
        or ""
    )

    text = str(raw).strip().lower()
    duration_match = re.search(
        r"(\d+\s*(?:hours?|days?|weeks?))",
        text,
    )
    if duration_match:
        return f"for {duration_match.group(1)}"
    if text.startswith("since "):
        return text
    if text:
        return f"for {text}" if re.search(r"\d", text) else text
    return ""


def _state_temperature(
    state: ClinicalState,
) -> float:

    nlice = state.get("nlice_data") or {}
    text = " ".join(
        [
            str(nlice.get("excitation") or ""),
            _latest_user_message(state.get("messages")),
            " ".join(
                str(getattr(message, "content", ""))
                for message in state.get("messages", [])
            ),
        ]
    )
    match = re.search(
        r"\b(9[5-9]|10[0-9]|11[0-5])(?:\.\d+)?\s*(?:f|fahrenheit)?\b",
        text,
        flags=re.IGNORECASE,
    )
    return float(match.group(0).lower().replace("fahrenheit", "").replace("f", "").strip()) if match else 0


def _has_high_fever(
    state: ClinicalState,
) -> bool:

    nlice = state.get("nlice_data") or {}
    text = " ".join(
        [
            str(state.get("complaint") or ""),
            str(nlice.get("nature") or ""),
            " ".join(state.get("associated_symptoms") or []),
        ]
    ).lower()

    return "fever" in text and _state_temperature(state) > 103


def _known_clinical_value(value) -> bool:

    if value is None:
        return False

    if isinstance(value, bool):
        return True

    return not _is_empty(value)


def _yes_no_reply(
    text: str,
) -> bool | None:

    normalized = (
        text or ""
    ).strip().lower()

    if re.search(r"\b(yes|yeah|yep|normal|normally|able|can)\b", normalized):
        return True

    if re.search(r"\b(no|nope|not|unable|can't|cannot|without|denies?|deny)\b", normalized):
        return False

    return None


def detect_workflow(
    state: ClinicalState,
) -> str | None:

    complaint = _clean_complaint_text(
        state.get("complaint"),
        state.get("nlice_data"),
    )
    symptoms = " ".join(
        state.get("associated_symptoms") or []
    )
    nlice = state.get("nlice_data") or {}
    text = " ".join(
        [
            str(state.get("complaint") or ""),
            str(complaint or ""),
            str(nlice.get("nature") or ""),
            symptoms,
        ]
    ).lower()

    workflow_key = workflow_key_for_complaint(text)
    if get_workflow(workflow_key):
        return workflow_key

    return None


def extract_clinical_fields(
    state: ClinicalState,
    user_text: str,
    latest_ai_text: str,
    nlice_data: dict,
    associated_symptoms: list[str],
    medications: str | None,
) -> dict:

    fields = dict(state.get("clinical_fields") or {})
    text = (user_text or "").lower()
    latest_question = (latest_ai_text or "").lower()
    symptom_polarity = _symptom_polarity_from_text(user_text)
    symptoms = {
        symptom.lower()
        for symptom in associated_symptoms or []
    }

    for symptom, is_positive in symptom_polarity.items():
        field_name = SYMPTOM_FIELD_NAMES.get(symptom)
        if field_name:
            fields[field_name] = is_positive

    if (
        symptom_polarity.get("cough") is True
        or symptom_polarity.get("breathing difficulty") is True
    ):
        fields["associated_respiratory_symptoms"] = True
    elif (
        symptom_polarity.get("cough") is False
        and symptom_polarity.get("breathing difficulty") is False
    ):
        fields["associated_respiratory_symptoms"] = False

    systemic_values = [
        symptom_polarity.get("weakness"),
        symptom_polarity.get("chills"),
        symptom_polarity.get("body aches"),
        symptom_polarity.get("sweating"),
    ]
    if any(value is True for value in systemic_values):
        fields["associated_systemic_symptoms"] = True
    elif systemic_values and all(value is False for value in systemic_values):
        fields["associated_systemic_symptoms"] = False

    red_flag_values = [
        symptom_polarity.get(symptom)
        for symptom in (
            "breathing difficulty",
            "confusion",
            "chest pain",
            "fainting",
            "vomiting",
            "weakness",
            "stiff neck",
            "rash",
        )
    ]
    if any(value is True for value in red_flag_values):
        fields["danger_red_flags"] = True
    elif red_flag_values and all(value is False for value in red_flag_values):
        fields["danger_red_flags"] = False

    duration = nlice_data.get("chronology")
    if duration and not _is_empty(duration):
        fields["duration"] = duration

    temp_match = re.search(
        r"\b(9[5-9]|10[0-9]|11[0-5])(?:\.\d+)?\s*(?:f|fahrenheit)?\b",
        text,
        flags=re.IGNORECASE,
    )
    if temp_match:
        fields["temperature_max"] = float(
            temp_match.group(0)
            .lower()
            .replace("fahrenheit", "")
            .replace("f", "")
            .strip()
        )
        fields["temperature_unit"] = "F"

    if (
        "cough" in symptoms
        or ("cough" in text and symptom_polarity.get("cough") is not False)
    ):
        fields["cough"] = True

    if "breathing difficulty" in symptoms or (
        symptom_polarity.get("breathing difficulty") is not False
        and re.search(
            r"\b(shortness of breath|difficulty breathing|breathing difficulty|trouble breathing)\b",
            text,
        )
    ):
        fields["breathing_difficulty"] = True

    if "weakness" in symptoms or (
        symptom_polarity.get("weakness") is not False
        and (
            "severe weakness" in text
            or re.search(r"\bweakness\b", text)
        )
    ):
        fields["weakness"] = True

    if (
        "vomiting" in symptoms
        or ("vomit" in text and symptom_polarity.get("vomiting") is not False)
    ):
        fields["vomiting"] = True

    if (
        "diarrhea" in symptoms
        or ("diarrhea" in text and symptom_polarity.get("diarrhea") is not False)
    ):
        fields["diarrhea"] = True

    if any(
        phrase in latest_question
        for phrase in (
            "cough, sore throat",
            "trouble breathing",
            "are you also having cough",
            "associated respiratory",
        )
    ):
        respiratory_answer = _yes_no_reply(user_text)
        if respiratory_answer is False:
            fields["cough"] = False
            fields["breathing_difficulty"] = False
        elif respiratory_answer is True:
            fields["associated_respiratory_symptoms"] = True

    if any(
        phrase in latest_question
        for phrase in (
            "vomiting or diarrhea",
            "vomit",
            "diarrhea",
        )
    ):
        gi_answer = _yes_no_reply(user_text)
        if gi_answer is False:
            fields["vomiting"] = False
            fields["diarrhea"] = False
        elif gi_answer is True:
            fields["vomiting"] = True

    if any(
        phrase in latest_question
        for phrase in (
            "chills",
            "body aches",
            "sweating",
            "severe weakness",
        )
    ):
        systemic_answer = _yes_no_reply(user_text)
        if systemic_answer is False:
            fields["chills"] = False
            fields["body_aches"] = False
            fields["sweating"] = False
            fields["weakness"] = False
            fields["associated_systemic_symptoms"] = False
        elif systemic_answer is True:
            fields["associated_systemic_symptoms"] = True

    if any(
        phrase in latest_question
        for phrase in (
            "anyone around you been sick",
            "covid",
            "flu",
            "travel",
            "mosquito exposure",
        )
    ):
        exposure_answer = _yes_no_reply(user_text)
        if exposure_answer is not None:
            fields["sick_contacts"] = exposure_answer

    medication_taken = _medication_taken_from_text(user_text)
    if medication_taken is None and any(
        phrase in latest_question
        for phrase in (
            "fever medicine",
            "taken any medicine",
            "taken any medication",
            "paracetamol",
            "acetaminophen",
            "ibuprofen",
        )
    ):
        medication_taken = _yes_no_reply(user_text)

    if medication_taken is False:
        fields["medication_taken"] = False
        fields.pop("medication_name", None)
        fields.pop("medication_response", None)
    elif medication_taken is True:
        fields["medication_taken"] = True

    if medications and fields.get("medication_taken") is not False:
        fields["medication_taken"] = True
        fields["medication_name"] = medications

    if fields.get("medication_taken") is not False and re.search(
        r"\b(paracetamol|acetaminophen|ibuprofen|aspirin|medicine|medication|tablet)\b",
        text,
    ):
        fields["medication_taken"] = True
        detected_names = [
            term
            for term in (
                "paracetamol",
                "acetaminophen",
                "ibuprofen",
                "aspirin",
            )
            if term in text
        ]
        if detected_names:
            fields["medication_name"] = ", ".join(
                dict.fromkeys(detected_names)
            )

    if any(
        phrase in latest_question
        for phrase in (
            "temperature come down",
            "fever come down",
            "did it come down",
            "did the temperature come down",
            "did the fever come down",
            "what is your temperature now",
        )
    ):
        if fields.get("medication_taken") is False:
            fields.pop("medication_response", None)
        else:
            response = _yes_no_reply(user_text)
            if response is True:
                fields["medication_response"] = "fever came down"
            elif response is False:
                fields["medication_response"] = "fever did not come down"
            elif re.search(r"\b(better|improved|came down|reduced|lower)\b", text):
                fields["medication_response"] = user_text.strip()
            elif re.search(r"\b(no change|same|still high|not better)\b", text):
                fields["medication_response"] = user_text.strip()

    if any(
        phrase in latest_question
        for phrase in (
            "drink fluids",
            "urinate normally",
            "keep fluids down",
            "urinating normally",
        )
    ):
        hydration_answer = _yes_no_reply(user_text)
        if hydration_answer is True:
            fields["hydration_status"] = (
                "drinking fluids and urinating normally"
            )
            fields["urination_normal"] = True
        elif hydration_answer is False:
            fields["hydration_status"] = (
                "not drinking fluids or urinating normally"
            )
            fields["urination_normal"] = False

    if any(
        phrase in latest_question
        for phrase in (
            "trouble breathing",
            "difficulty breathing",
            "shortness of breath",
            "breathing difficulty",
        )
    ):
        breathing_answer = _yes_no_reply(user_text)
        if breathing_answer is not None:
            fields["breathing_difficulty"] = breathing_answer

    if any(
        phrase in latest_question
        for phrase in (
            "severe weakness",
            "weakness",
        )
    ):
        weakness_answer = _yes_no_reply(user_text)
        if weakness_answer is not None:
            fields["weakness"] = weakness_answer

    if any(
        phrase in latest_question
        for phrase in (
            "red flag",
            "trouble breathing",
            "confusion",
            "chest pain",
            "fainting",
            "rash",
            "dehydration",
        )
    ):
        red_flag_answer = _yes_no_reply(user_text)
        if red_flag_answer is False:
            fields["danger_red_flags"] = False
        elif red_flag_answer is True and red_flag_values:
            fields["danger_red_flags"] = True

    return fields


def _workflow_field_complete(
    field: str,
    state: ClinicalState,
) -> bool:

    clinical_fields = state.get("clinical_fields") or {}
    nlice = state.get("nlice_data") or {}

    if field == "duration":
        return _known_clinical_value(
            clinical_fields.get("duration")
            or nlice.get("chronology")
        )

    if field == "associated_respiratory_symptoms":
        if _known_clinical_value(
            clinical_fields.get("associated_respiratory_symptoms")
        ):
            return True
        return any(
            _known_clinical_value(clinical_fields.get(key))
            for key in (
                "cough",
                "breathing_difficulty",
                "shortness_of_breath",
                "wheezing",
            )
        )

    if field == "associated_systemic_symptoms":
        return any(
            _known_clinical_value(clinical_fields.get(key))
            for key in (
                "weakness",
                "chills",
                "body_aches",
                "sweating",
            )
        )

    if field == "medication_taken":

        if clinical_fields.get("medication_taken") is not None:
            return True

        return _known_clinical_value(
            clinical_fields.get("medication_name")
        )

    if field == "hydration_status":
        return _known_clinical_value(
            clinical_fields.get("hydration_status")
        ) or _known_clinical_value(
            clinical_fields.get("urination_normal")
        )

    if field == "vomiting_diarrhea":
        return any(
            _known_clinical_value(clinical_fields.get(key))
            for key in ("vomiting", "diarrhea")
        )

    if field == "danger_red_flags":
        return bool(state.get("red_flags_screened")) or _known_clinical_value(
            clinical_fields.get("danger_red_flags")
        )

    if field == "exposure_infection":
        return any(
            _known_clinical_value(clinical_fields.get(key))
            for key in (
                "sick_contacts",
                "covid_flu_test",
                "travel_or_mosquito_exposure",
            )
        )

    return _known_clinical_value(clinical_fields.get(field))


def _workflow_dependencies(
    workflow: dict,
    field: str,
) -> list[str]:

    return list(
        (workflow.get("field_dependencies") or {}).get(field, [])
    )


def _workflow_field_skipped(
    field: str,
    state: ClinicalState,
    workflow: dict,
) -> bool:

    clinical_fields = state.get("clinical_fields") or {}

    for dependency in _workflow_dependencies(workflow, field):
        dependency_value = clinical_fields.get(dependency)
        if dependency_value is False:
            return True

    return False


def _workflow_dependencies_ready(
    field: str,
    state: ClinicalState,
    workflow: dict,
) -> bool:

    for dependency in _workflow_dependencies(workflow, field):
        if not _workflow_field_complete(dependency, state):
            return False

    return True


def get_missing_workflow_fields(
    state: ClinicalState,
) -> list[str]:

    workflow_key = state.get("workflow_key")
    workflow = get_workflow(workflow_key or "")

    if not workflow:
        return []

    missing_fields: list[str] = []

    for field in workflow.get("required_fields", []):
        if _workflow_field_complete(field, state):
            continue
        if _workflow_field_skipped(field, state, workflow):
            continue
        if not _workflow_dependencies_ready(field, state, workflow):
            continue
        missing_fields.append(field)

    if workflow_key == "fever":
        clinical_fields = state.get("clinical_fields") or {}
        try:
            temperature = float(clinical_fields.get("temperature_max") or 0)
        except (TypeError, ValueError):
            temperature = 0
        fever_completion_fields = [
            "hydration_status",
            "medication_response",
            "exposure_infection",
        ]
        if temperature > 103:
            fever_completion_fields.append("associated_systemic_symptoms")
        for field in fever_completion_fields:
            if field in missing_fields:
                continue
            if _workflow_field_skipped(field, state, workflow):
                continue
            if not _workflow_dependencies_ready(field, state, workflow):
                continue
            if not _workflow_field_complete(field, state):
                missing_fields.append(field)

    return missing_fields


def get_next_workflow_question(
    state: ClinicalState,
) -> tuple[str, str] | None:

    workflow_key = state.get("workflow_key")
    workflow = get_workflow(workflow_key or "")

    if not workflow:
        return None

    missing_fields = set(
        get_missing_workflow_fields(state)
    )
    if not missing_fields:
        return None

    clinical_fields = state.get("clinical_fields") or {}
    priority_order = list(
        workflow.get("priority_order") or []
    )

    temperature = clinical_fields.get("temperature_max")
    try:
        temperature_value = float(temperature or 0)
    except (TypeError, ValueError):
        temperature_value = 0

    if workflow_key == "fever" and temperature_value >= 105:
        priority_order = [
            "danger_red_flags",
            "medication_taken",
            "medication_response",
            *priority_order,
        ]
    elif workflow_key == "fever" and temperature_value > 103:
        priority_order = [
            "danger_red_flags",
            "medication_taken",
            "medication_response",
            "hydration_status",
            "vomiting_diarrhea",
            *priority_order,
        ]

    chest_pain = clinical_fields.get("chest_pain")
    breathing_difficulty = clinical_fields.get("breathing_difficulty")
    if chest_pain is True and breathing_difficulty is True:
        priority_order = [
            "danger_red_flags",
            "cardiac_red_flags",
            "shortness_of_breath",
            "breathing_difficulty",
            *priority_order,
        ]
    elif breathing_difficulty is True or clinical_fields.get("cough") is True:
        priority_order = [
            "shortness_of_breath",
            "associated_respiratory_symptoms",
            "danger_red_flags",
            *priority_order,
        ]
    elif clinical_fields.get("weakness") is True:
        priority_order = [
            "associated_systemic_symptoms",
            "danger_red_flags",
            *priority_order,
        ]

    field_questions = workflow.get("field_questions") or {}

    seen = set()
    for field in priority_order:
        if field in seen:
            continue
        seen.add(field)
        if (
            field in missing_fields
            and field in field_questions
            and not _workflow_field_skipped(field, state, workflow)
        ):
            return field, field_questions[field]

    for field in workflow.get("required_fields", []):
        if (
            field in missing_fields
            and field in field_questions
            and not _workflow_field_skipped(field, state, workflow)
        ):
            return field, field_questions[field]

    return None


def _negative_findings_from_messages(
    state: ClinicalState,
) -> list[str]:

    findings: list[str] = []
    messages = state.get("messages") or []

    targets = {
        "breathing difficulty": r"breath|breathing|shortness of breath",
        "chest pain": r"chest pain|chest pressure",
        "vomiting": r"vomit|vomiting",
        "diarrhea": r"diarrhea|loose motion|loose stool",
        "dizziness": r"dizziness|dizzy|faint",
    }

    for message in messages:
        if getattr(message, "type", None) != "human":
            continue

        answer = str(getattr(message, "content", "")).lower()

        if not re.search(
            r"\b(no|not|none|without|denies?|deny)\b",
            answer
        ):
            continue

        for label, pattern in targets.items():
            if re.search(pattern, answer):
                findings.append(label)

    return list(dict.fromkeys(findings))

def _negative_findings_from_fields(
    state: ClinicalState,
) -> list[str]:

    clinical_fields = state.get("clinical_fields") or {}
    captured_negatives = set(_negative_findings_from_messages(state))
    labels = {
        "cough": "cough",
        "breathing_difficulty": "breathing difficulty",
        "chest_pain": "chest pain",
        "vomiting": "vomiting",
        "diarrhea": "diarrhea",
        "rash": "rash",
        "confusion": "confusion",
        "weakness": "weakness",
    }

    print("CLINICAL FIELDS:", clinical_fields)

    return [
        # label
        # for field, label in labels.items()
        # if clinical_fields.get(field) is False and label in captured_negatives
    ]


def _normalize_clinical_summary(
    state: ClinicalState,
    raw_summary: str | None = None,
) -> str:

    nlice = state.get("nlice_data") or {}
    complaint = _clean_complaint_text(
        state.get("complaint"),
        nlice,
    )
    duration = _normalized_duration(state)
    symptoms = [
        symptom
        for symptom in _filter_symptoms_by_clinical_fields(
            state.get("associated_symptoms"),
            state.get("clinical_fields"),
        )
        if symptom != complaint
    ]
    negatives = list(
        dict.fromkeys(
            [
                *_negative_findings_from_fields(state),
                *_negative_findings_from_messages(state),
            ]
        )
    )
    print("MESSAGE NEGATIVES:", _negative_findings_from_messages(state))
    print("FIELD NEGATIVES:", _negative_findings_from_fields(state))
    
    print("NEGATIVES USED IN SUMMARY:", negatives)
    age_gender = str(
        state.get("age_gender") or "Patient"
    ).strip()

    subject = age_gender
    if subject.lower() == "patient":
        subject = "Patient"

    summary_parts = [
        f"{subject} presenting with {complaint}"
    ]

    if duration:
        summary_parts[0] = (
            f"{summary_parts[0]} {duration}"
        )

    if symptoms:
        summary_parts.append(
            "associated with "
            + ", ".join(symptoms)
        )

    temperature = _state_temperature(state)
    if temperature:
        summary_parts.append(
            f"maximum recorded temperature {temperature:g} F"
        )

    if negatives:
        summary_parts.append(
            "denies " + " and ".join(negatives)
        )

    if nlice.get("intensity"):
        summary_parts.append(
            f"severity {nlice.get('intensity')}/10"
        )

    if state.get("medications"):
        summary_parts.append(
            f"medication taken: {state.get('medications')}"
        )

    if temperature > 103:
        summary_parts.append(
            "findings warrant elevated clinical attention due to high fever"
        )

    normalized = ". ".join(
        part.strip(" .")
        for part in summary_parts
        if part
    )

    normalized = re.sub(
        r"\b(\d+\s*(?:hours?|days?|weeks?))\s+\1\b",
        r"\1",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(r"\s+", " ", normalized).strip()

    if normalized:
        return normalized[0].upper() + normalized[1:] + "."
    

    

    return (raw_summary or "Clinical summary pending.").strip()


def _extract_lab_report_values(
    vision_output,
) -> dict:

    if isinstance(vision_output, dict):
        text = json.dumps(vision_output)
    else:
        text = str(vision_output or "")

    patterns = {
        "hemoglobin": r"\b(?:hb|hemoglobin)\b[^0-9]{0,20}(\d+(?:\.\d+)?)\s*(?:g/dl|gm/dl|g%)?",
        "wbc": r"\b(?:wbc|white\s+blood\s+cells?|total\s+leucocyte\s+count|tlc)\b[^0-9]{0,20}(\d+(?:,\d{3})*(?:\.\d+)?)",
        "platelets": r"\b(?:platelets?|platelet\s+count|plt)\b[^0-9]{0,20}(\d+(?:,\d{3})*(?:\.\d+)?)",
        "glucose": r"\b(?:glucose|blood\s+sugar|rbs|fbs)\b[^0-9]{0,20}(\d+(?:\.\d+)?)",
        "creatinine": r"\b(?:creatinine|serum\s+creatinine)\b[^0-9]{0,20}(\d+(?:\.\d+)?)",
    }
    values = {}

    for key, pattern in patterns.items():
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            values[key] = match.group(1).replace(",", "")

    bp_match = re.search(
        r"\b(?:bp|blood\s+pressure)\b[^0-9]{0,20}(\d{2,3})\s*/\s*(\d{2,3})",
        text,
        flags=re.IGNORECASE,
    )
    if bp_match:
        values["bp"] = f"{bp_match.group(1)}/{bp_match.group(2)}"

    return values


def _classify_case_type(
    state: ClinicalState,
) -> str:

    nlice = state.get("nlice_data") or {}
    clinical_fields = state.get("clinical_fields") or {}
    symptoms = _filter_symptoms_by_clinical_fields(
        state.get("associated_symptoms"),
        clinical_fields,
    )
    text = " ".join(
        [
            str(state.get("complaint") or ""),
            str(nlice.get("nature") or ""),
            " ".join(symptoms),
        ]
    ).lower()

    if (
        clinical_fields.get("chest_pain") is True
        or (
            "chest pain" in text
            and clinical_fields.get("chest_pain") is not False
        )
        or (
            "sweating" in text
            and clinical_fields.get("sweating") is not False
        )
    ):
        return "cardiac"
    if (
        ("breath" in text and clinical_fields.get("breathing_difficulty") is not False)
        or ("cough" in text and clinical_fields.get("cough") is not False)
    ):
        return "respiratory"
    if "fever" in text and re.search(r"vomit|nausea|diarrhea", text) and not (
        clinical_fields.get("vomiting") is False
        and clinical_fields.get("diarrhea") is False
    ):
        return "infectious_gi"
    if "fever" in text:
        return "fever"
    if re.search(r"vomit|nausea|diarrhea|abdominal|stomach", text) and not (
        clinical_fields.get("vomiting") is False
        and clinical_fields.get("diarrhea") is False
    ):
        return "gastrointestinal"
    return "general"


def _generate_recommendations(
    state: ClinicalState,
) -> list[str]:

    case_type = _classify_case_type(state)
    urgency = str(
        state.get("urgency") or ""
    ).lower()
    symptoms = _filter_symptoms_by_clinical_fields(
        state.get("associated_symptoms"),
        state.get("clinical_fields"),
    )
    recs: list[str] = []

    if case_type == "cardiac":
        recs.extend(
            [
                "Seek urgent clinical evaluation for chest pain.",
                "Avoid exertion and remain seated or resting while awaiting care.",
                "Escalate immediately if pain worsens, spreads, or breathing becomes difficult.",
            ]
        )
    elif case_type == "respiratory":
        recs.extend(
            [
                "Monitor breathing effort and ability to speak full sentences.",
                "Seek urgent evaluation if shortness of breath occurs at rest or worsens.",
                "Avoid exertion until respiratory symptoms are assessed.",
            ]
        )
    elif case_type in {"fever", "infectious_gi"}:
        recs.extend(
            [
                "Maintain hydration with small frequent fluids.",
                "Monitor temperature and symptom progression.",
                "Use fever medication only as clinically advised and confirm dose timing.",
            ]
        )
        if "vomiting" in symptoms:
            recs.append(
                "Escalate if vomiting persists or fluids cannot be kept down."
            )
    elif case_type == "gastrointestinal":
        recs.extend(
            [
                "Monitor fluid intake, urine output, and vomiting or diarrhea frequency.",
                "Use small frequent fluids and seek care if dehydration signs appear.",
            ]
        )
    else:
        recs.extend(
            [
                "Continue monitoring symptoms and note any worsening pattern.",
                "Seek medical review if symptoms persist, worsen, or new red flags appear.",
            ]
        )

    if urgency in {"emergency", "urgent", "high"}:
        recs.insert(
            0,
            "Treat this as urgent and arrange prompt medical assessment.",
        )

    deduped = []
    for rec in recs:
        if rec not in deduped:
            deduped.append(rec)

    return deduped[:5]


def _validate_clinical_state(
    state: ClinicalState,
) -> tuple[ClinicalState, list[str]]:

    next_state = dict(state)
    warnings = []
    symptoms = _filter_symptoms_by_clinical_fields(
        next_state.get("associated_symptoms"),
        next_state.get("clinical_fields"),
    )
    complaint = _clean_complaint_text(
        next_state.get("complaint"),
        next_state.get("nlice_data"),
    )

    if complaint and complaint not in {"symptoms", "fever"}:
        symptoms = _normalize_symptom_list(
            [*symptoms, complaint]
        )

    negative_symptoms = set(
        _negative_findings_from_fields(next_state)
    )
    if negative_symptoms:
        symptoms = [
            symptom
            for symptom in symptoms
            if symptom not in negative_symptoms
        ]

    if "breathing difficulty" in symptoms:
        warnings.append(
            "Breathing symptom present; ensure respiratory card does not show negative status."
        )

    if "chest pain" in symptoms and "chest pain" not in complaint:
        warnings.append(
            "Chest pain appears as associated symptom but not primary complaint."
        )

    next_state["associated_symptoms"] = symptoms
    next_state["validation_warnings"] = warnings
    return next_state, warnings


def _exploration_is_complete(
    state: ClinicalState,
) -> bool:

    exploration_questions = (
        state.get("exploration_questions")
        or []
    )

    if _has_high_fever(state) and not _priority_followups_complete(state):
        return False

    if (
        _has_red_flag(
            _latest_user_message(
                state.get("messages")
            )
        )
        and _priority_followups_complete(state)
    ):
        return True

    return (
        len(exploration_questions) >= 2
        and bool(state.get("red_flags_screened"))
        and _priority_followups_complete(state)
    )


def _select_question_focus(
    state: ClinicalState,
    missing_fields: list[str],
) -> tuple[str, str | None]:
    """
    Decide the conversational priority while keeping orchestration deterministic.

    Returns (mode, target), where mode is either "exploration" or "nlice".
    """

    exploration_questions = (
        state.get("exploration_questions")
        or []
    )
    associated_symptoms = (
        state.get("associated_symptoms")
        or []
    )

    if _priority_followup_question(state):
        return "exploration", "priority_followup"

    if not exploration_questions:
        return "exploration", "associated_symptoms"

    if (
        associated_symptoms
        and missing_fields
        and len(exploration_questions) < 2
    ):
        return "exploration", "nlice_blend"

    if not state.get("red_flags_screened"):
        return "exploration", "red_flags"

    if missing_fields:
        return "nlice", missing_fields[0]

    if len(exploration_questions) < 2:
        return "exploration", "contextual_followup"

    return "nlice", None


def _conversation_target_field(
    current_nlice: dict,
    messages: list[BaseMessage] | None,
) -> str | None:
    """
    Infer which NLICE slot the patient's short reply is probably answering.

    Deterministic missing-field order remains the primary source of truth.
    The latest assistant question is used as supporting context when the
    patient replies with a terse answer such as "no" or "8".
    """

    missing_fields = _missing_nlice_fields(
        current_nlice
    )

    if not missing_fields:
        return None

    latest_ai_text = (
        _latest_ai_message(messages)
        .strip()
        .lower()
    )

    question_field_hints = {
        "intensity": [
            "how severe",
            "severity",
            "scale from 1 to 10",
            "scale of 1 to 10",
            "scale 1 to 10",
            "out of 10",
            "pain scale",
            "rate",
        ],
        "excitation": [
            "better or worse",
            "make it better",
            "makes it better",
            "make it worse",
            "makes it worse",
            "worsen",
            "trigger",
            "improve",
            "relieve",
            "after medication",
            "after medicine",
        ],
        "chronology": [
            "when did",
            "how long",
            "started",
            "start",
            "duration",
            "since when",
        ],
        "location": [
            "where",
            "which part",
            "location",
            "exactly are you feeling",
        ],
        "nature": [
            "what does",
            "describe",
            "feel like",
            "kind of",
            "type of",
        ],
    }

    for field, hints in question_field_hints.items():
        if field in missing_fields and any(
            hint in latest_ai_text
            for hint in hints
        ):
            return field

    return missing_fields[0]


def _normalize_contextual_reply(
    user_text: str,
    target_field: str | None,
    latest_ai_text: str,
) -> dict:
    """
    Normalize short patient replies using the current NLICE target and
    previous assistant question context.
    """

    text = (user_text or "").strip()
    text_lower = text.lower()
    compact = re.sub(
        r"\s+",
        " ",
        text_lower,
    ).strip(" .?!,;")

    normalized: dict = {}

    negative_replies = {
        "no",
        "nope",
        "nah",
        "nothing",
        "none",
        "not really",
        "no nothing",
        "nothing really",
        "no idea",
        "not sure",
    }

    if target_field == "excitation":
        if compact in negative_replies:
            normalized["excitation"] = "none"
            return normalized

        if (
            any(
                medicine in compact
                for medicine in [
                    "medicine",
                    "medication",
                    "tablet",
                    "tablets",
                    "paracetamol",
                    "acetaminophen",
                    "ibuprofen",
                ]
            )
            and any(
                cue in compact
                for cue in [
                    "yes",
                    "after",
                    "with",
                    "helps",
                    "improves",
                    "better",
                ]
            )
        ):
            normalized["excitation"] = (
                f"improves with {compact}"
            )
            return normalized

        if compact in {
            "medicine",
            "medication",
            "tablet",
            "tablets",
            "paracetamol",
            "after medicine",
            "after medication",
        }:
            normalized["excitation"] = (
                f"improves with {compact}"
            )
            return normalized

    if target_field == "intensity":
        standalone_intensity = re.fullmatch(
            r"(10|[1-9])(?:\s*/\s*10)?",
            compact,
        )

        if standalone_intensity:
            normalized["intensity"] = (
                standalone_intensity.group(1)
            )
            return normalized

    if target_field == "chronology":
        if compact in {
            "today",
            "yesterday",
            "this morning",
            "morning",
            "last night",
        }:
            normalized["chronology"] = (
                "since morning"
                if compact == "morning"
                else f"since {compact}"
            )
            return normalized

    if target_field == "location":
        location_prompt = any(
            phrase in latest_ai_text
            for phrase in [
                "where",
                "which part",
                "location",
            ]
        )
        if location_prompt and 1 <= len(compact.split()) <= 4:
            normalized["location"] = compact
            return normalized

    return normalized



def _json_from_text(text: str) -> dict:

    raw_text = (text or "").strip()

    if raw_text.startswith("```"):

        raw_text = re.sub(
            r"^```(?:json)?",
            "",
            raw_text,
            flags=re.IGNORECASE,
        ).strip()

        raw_text = re.sub(
            r"```$",
            "",
            raw_text,
        ).strip()

    try:
        return json.loads(raw_text)

    except json.JSONDecodeError:

        match = re.search(
            r"\{.*\}",
            raw_text,
            flags=re.DOTALL,
        )

        if match:
            return json.loads(match.group(0))

        raise


# =========================================================
# EXTRACT INFO NODE
# =========================================================

# =========================================================
# EXTRACT INFO NODE
# =========================================================

def extract_info_node(
    state: ClinicalState,
) -> dict:

    user_text = _latest_user_message(
        state.get("messages")
    )

    user_text_lower = user_text.lower()
    latest_ai_text = _latest_ai_message(
        state.get("messages")
    ).lower()

    current_nlice = (
        state.get("nlice_data")
        or _empty_nlice()
    )
    associated_symptoms = _extract_associated_symptoms(
        user_text=user_text,
        existing_symptoms=state.get(
            "associated_symptoms"
        ),
    )
    red_flags_screened = bool(
        state.get("red_flags_screened")
    )
    concept_memory = _update_concept_memory(
        state=state,
        user_text=user_text,
        latest_ai_text=latest_ai_text,
    )
    uncertainty_count = int(
        state.get("uncertainty_count") or 0
    )

    if _is_uncertain_reply(user_text):
        uncertainty_count += 1

    if any(
        term in latest_ai_text
        for term in [
            "breathing difficulty",
            "difficulty breathing",
            "confusion",
            "chest pain",
            "fainting",
            "severe weakness",
            "persistent vomiting",
            "stiff neck",
        ]
    ):
        red_flags_screened = True

    updated_nlice = {
        **current_nlice
    }

    target_field = _conversation_target_field(
        current_nlice,
        state.get("messages"),
    )

    contextual_normalization = (
        _normalize_contextual_reply(
            user_text=user_text,
            target_field=target_field,
            latest_ai_text=latest_ai_text,
        )
    )

    for key, value in contextual_normalization.items():
        if key in NLICE_FIELDS and not _is_missing_nlice_value(
            key,
            value,
        ):
            updated_nlice[key] = value

    # -----------------------------------------------------
    # RULE-BASED EXTRACTION
    # -----------------------------------------------------

    BODY_PARTS = [
        "chest",
        "head",
        "stomach",
        "abdomen",
        "back",
        "leg",
        "arm",
        "throat",
    ]

    PAIN_TYPES = [
        "sharp",
        "burning",
        "dull",
        "throbbing",
        "stabbing",
        "cramping",
        "aching",
        "pressure",
        "tightness",
        "squeezing",
        "heavy",
    ]

    SYSTEMIC_TERMS = [
        "fever",
        "fatigue",
        "weakness",
        "dizziness",
        "chills",
        "body ache",
    ]

    # -----------------------------------------------------
    # INTENSITY
    # -----------------------------------------------------

    intensity_patterns = [
        r"\b(?:severity|severe|pain scale|scale|rate|rating)\D{0,20}\b(10|[1-9])\b",
        r"\b(10|[1-9])\s*(?:/|out of)\s*10\b",
        r"\b(10|[1-9])\s*(?:on|in)\s*(?:a\s*)?(?:pain\s*)?scale\b",
    ]

    explicit_intensity_found = False

    for pattern in intensity_patterns:

        intensity_match = re.search(
            pattern,
            user_text_lower,
        )

        if intensity_match:

            explicit_intensity_found = True
            updated_nlice["intensity"] = (
                intensity_match.group(1)
            )
            break

    if not explicit_intensity_found:

        asked_for_intensity = any(
            phrase in latest_ai_text
            for phrase in [
                "how severe",
                "severity",
                "scale from 1 to 10",
                "scale of 1 to 10",
                "scale 1 to 10",
                "out of 10",
                "pain scale",
                "rate",
            ]
        )

        standalone_intensity = re.fullmatch(
            r"\s*(10|[1-9])\s*",
            user_text_lower,
        )

        if (
            asked_for_intensity
            and standalone_intensity
            and _is_missing_nlice_value(
                "intensity",
                updated_nlice.get("intensity"),
            )
        ):

            explicit_intensity_found = True
            updated_nlice["intensity"] = (
                standalone_intensity.group(1)
            )

    # -----------------------------------------------------
    # LOCATION
    # -----------------------------------------------------

    for body in BODY_PARTS:

        if body in user_text_lower:

            updated_nlice["location"] = body
            break

    # -----------------------------------------------------
    # FEVER DETECTION
    # -----------------------------------------------------

    if "fever" in user_text_lower:

        updated_nlice["nature"] = "fever"

    # -----------------------------------------------------
    # NATURE
    # -----------------------------------------------------

    for pain in PAIN_TYPES:

        if pain in user_text_lower:

            updated_nlice["nature"] = pain
            break

    medications = state.get("medications")
    medication_terms = [
        "paracetamol",
        "acetaminophen",
        "ibuprofen",
        "aspirin",
    ]

    medication_taken = _medication_taken_from_text(user_text)
    detected_medications = []
    if medication_taken is not False:
        detected_medications = [
            term
            for term in medication_terms
            if term in user_text_lower
        ]
    else:
        medications = None

    if detected_medications:
        medications = ", ".join(
            dict.fromkeys(detected_medications)
        )

    # -----------------------------------------------------
    # SYSTEMIC
    # -----------------------------------------------------

    if any(
        term in user_text_lower
        for term in SYSTEMIC_TERMS
    ):

        if _is_empty(
            updated_nlice.get("location")
        ):

            updated_nlice["location"] = (
                "Systemic/General"
            )

    # -----------------------------------------------------
    # CHRONOLOGY
    # -----------------------------------------------------

    duration_match = re.search(
        r"(\d+\s*(hours?|days?|weeks?))",
        user_text_lower,
    )

    if duration_match:

        updated_nlice["chronology"] = (
            duration_match.group(1)
        )



    # -----------------------------------------------------
    # CLOCK TIME DETECTION
    # -----------------------------------------------------

    time_match = re.search(
        r"(\\d{1,2}\\s?(am|pm))",
        user_text_lower,
    )

    if time_match:

        updated_nlice["chronology"] = (
            f"started at {time_match.group(1)}"
        )

    # -----------------------------------------------------
    # MORNING / YESTERDAY DETECTION
    # -----------------------------------------------------

    if "morning" in user_text_lower:

        updated_nlice["chronology"] = (
            "since morning"
        )

    if "yesterday" in user_text_lower:

        updated_nlice["chronology"] = (
            "since yesterday"
        )

    # -----------------------------------------------------
    # EXCITATION
    # -----------------------------------------------------

    excitation_patterns = [
        r"\b(?:better|worse)\b(?:\s+(?:with|when|on|after|during|while|by)\s+[^.?!,;]+)?",
        r"\b[^.?!,;]*(?:makes?|make|gets?|get|feels?|feel)\s+(?:it\s+)?(?:better|worse)\b",
        r"\b(?:with|when|on|after|during|while|by)\s+[^.?!,;]+\s+(?:it\s+)?(?:gets?|get|feels?|feel|becomes?|become)?\s*(?:better|worse)\b",
    ]

    for pattern in excitation_patterns:

        excitation_match = re.search(
            pattern,
            user_text_lower,
        )

        if excitation_match:

            excitation = (
                excitation_match.group(0)
                .strip(" .?!,;")
            )

            if excitation:

                updated_nlice["excitation"] = excitation
                break

    # -----------------------------------------------------
    # COMPLAINT
    # -----------------------------------------------------

    complaint = (
        state.get("complaint")
        or user_text
    )

    # -----------------------------------------------------
    # FALLBACK GEMINI EXTRACTION
    # -----------------------------------------------------

    missing_fields = _missing_nlice_fields(
        updated_nlice
    )

    # Only use Gemini if many fields missing

    if (
        len(missing_fields) >= 3
        and not contextual_normalization
    ):

        try:

            prompt = f"""
Extract clinical information.

Patient:
{user_text}

Return ONLY JSON.

{{
    "nlice_data": {{
        "nature": "",
        "location": "",
        "intensity": "",
        "chronology": "",
        "excitation": ""
    }}
}}
"""

            response = client.models.generate_content(
                model="gemini-1.5-flash",
                contents=[prompt],
            )

            parsed = _json_from_text(
                response.text
            )

            llm_nlice = (
                parsed.get(
                    "nlice_data",
                    {},
                )
            )

            for key, value in llm_nlice.items():

                if (
                    key == "intensity"
                    and not explicit_intensity_found
                ):

                    continue

                if (
                    _is_empty(
                        updated_nlice.get(key)
                    )
                    and not _is_empty(value)
                ):

                    updated_nlice[key] = value

        except Exception as exc:

            print(
                "Fallback extraction failed:",
                exc,
            )

    workflow_probe_state = {
        **state,
        "complaint": complaint,
        "nlice_data": updated_nlice,
        "associated_symptoms": associated_symptoms,
    }
    workflow_key = (
        state.get("workflow_key")
        or detect_workflow(workflow_probe_state)
    )
    clinical_fields = extract_clinical_fields(
        state={
            **workflow_probe_state,
            "workflow_key": workflow_key,
        },
        user_text=user_text,
        latest_ai_text=latest_ai_text,
        nlice_data=updated_nlice,
        associated_symptoms=associated_symptoms,
        medications=medications,
    )

    extracted_state = {

        "complaint": complaint,

        "nlice_data": updated_nlice,

        "associated_symptoms": associated_symptoms,

        "red_flags_screened": red_flags_screened,

        "concept_memory": concept_memory,

        "uncertainty_count": uncertainty_count,

        "medications": medications,

        "workflow_key": workflow_key,

        "clinical_fields": clinical_fields,
    }

    validated_state, validation_warnings = (
        _validate_clinical_state(
            {
                **state,
                **extracted_state,
            }
        )
    )

    extracted_state["associated_symptoms"] = (
        validated_state.get("associated_symptoms", associated_symptoms)
    )
    extracted_state["validation_warnings"] = validation_warnings
    return extracted_state


# =========================================================
# QUESTION NODE
# =========================================================


def question_node(
    state: ClinicalState,
) -> dict:

    workflow_question = get_next_workflow_question(state)

    MAX_QUESTIONS = 8 if (
        workflow_question or _priority_followup_question(state)
    ) else 5

    questions = list(
        state.get("questions") or []
    )
    exploration_questions = list(
        state.get("exploration_questions") or []
    )

    # ---------------------------------------------------
    # LOOP PROTECTION
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

    if workflow_question:
        _workflow_field, question = workflow_question

        questions.append(question)
        exploration_questions.append(question)

        return {

            "messages": [
                AIMessage(content=question)
            ],

            "questions": questions,

            "exploration_questions": exploration_questions,

            "current_question_index": (
                len(questions) - 1
            ),

            "clinical_fields": (
                state.get("clinical_fields") or {}
            ),

            "workflow_key": state.get("workflow_key"),
        }

    missing_fields = _missing_nlice_fields(
        state.get("nlice_data")
    )

    mode, target = _select_question_focus(
        state,
        missing_fields,
    )

    if not target:
        return {}

    complaint = (
        state.get("complaint") or ""
    )
    concept_memory = (
        state.get("concept_memory") or {}
    )
    uncertain_concepts = set(
        concept_memory.get("uncertain", [])
    )
    target_concept = CONCEPT_FOR_TARGET.get(
        str(target)
    )

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

    EXPLORATION_FALLBACK_MAP = {

    "associated_symptoms":
        "I'm sorry you're not feeling well. Have you noticed chills, cough, body aches, vomiting, breathing trouble, or headache along with it?",

    "red_flags":
        "Are you having any breathing difficulty, confusion, severe weakness, persistent vomiting, chest pain, or fainting?",

    "contextual_followup":
        "What other changes have you noticed since this started?",

    "nlice_blend":
        "Have you checked the temperature, and does it improve after medication or worsen at certain times?",

    "priority_followup":
        "Are you having breathing difficulty, confusion, severe weakness, persistent vomiting, chest pain, fainting, stiff neck, rash, or signs of dehydration?",
    }

    question = ""
    priority_followup = _priority_followup_question(state)

    if mode == "exploration" and priority_followup:
        target_concept, candidate_question = priority_followup
        previous_questions = [
            q.lower().strip()
            for q in questions
        ]
        if not _is_semantically_redundant_question(
            candidate_question,
            previous_questions,
            concept_memory,
            target_concept,
        ):
            question = candidate_question

    # ---------------------------------------------------
    # RETRIEVAL-AUGMENTED CLINICAL EXPLORATION
    # ---------------------------------------------------

    if mode == "exploration" and not question:

        try:

            result = clinical_exploration_agent(
                complaint=complaint,
                focus=str(target),
                nlice_state=state.get(
                    "nlice_data"
                ),
                associated_symptoms=state.get(
                    "associated_symptoms"
                ),
                missing_nlice_fields=missing_fields,
                previous_questions=questions,
                conversation_context=(
                    _compact_conversation_context(
                        state.get("messages")
                    )
                ),
            )

            candidate_question = (
                result.get("question") or ""
            ).strip()

            previous_questions = [
                q.lower().strip()
                for q in questions
            ]

            if (
                candidate_question
                and not _is_semantically_redundant_question(
                    candidate_question,
                    previous_questions,
                    concept_memory,
                    str(target),
                )
            ):
                question = candidate_question

        except Exception as exc:

            print(
                "Clinical exploration agent failed:",
                exc,
            )

    # ---------------------------------------------------
    # RETRIEVAL-AUGMENTED NLICE QUESTIONING
    # ---------------------------------------------------

    if mode == "nlice" and target:

        try:

            result = followup_question_agent(
                complaint=complaint,
                nlice_state=state.get(
                    "nlice_data"
                ),
                target_field=str(target),
                associated_symptoms=state.get(
                    "associated_symptoms"
                ),
                previous_questions=questions,
                conversation_context=(
                    _compact_conversation_context(
                        state.get("messages")
                    )
                ),
            )

            candidate_question = (
                result.get("question") or ""
            ).strip()

            previous_questions = [
                q.lower().strip()
                for q in questions
            ]

            if (
                candidate_question
                and not _is_semantically_redundant_question(
                    candidate_question,
                    previous_questions,
                    concept_memory,
                    str(target),
                )
            ):
                question = candidate_question

        except Exception as exc:

            print(
                "Question agent failed:",
                exc,
            )

    # ---------------------------------------------------
    # STATIC FALLBACK QUESTION
    # ---------------------------------------------------

    if (
        not question
        and target_concept in uncertain_concepts
    ):
        question = _uncertainty_followup(
            target_concept
        )

    if not question:

        if mode == "exploration":
            question = EXPLORATION_FALLBACK_MAP.get(
                str(target),
                "What other symptoms have you noticed?",
            )
        else:
            question = FIELD_QUESTION_MAP.get(
                str(target),
                "Can you tell me more?",
            )

        if _is_semantically_redundant_question(
            question,
            questions,
            concept_memory,
            str(target),
        ):
            question = _next_unexplored_question(
                state,
                str(target),
            )

    questions.append(question)

    if mode == "exploration":
        exploration_questions.append(question)

    return {

        "messages": [
            AIMessage(content=question)
        ],

        "questions": questions,

        "exploration_questions": exploration_questions,

        "current_question_index": (
            len(questions) - 1
        ),
    }


# =========================================================
# SUMMARY NODE
# =========================================================


def summary_node(
    state: ClinicalState,
) -> dict:

    app_state = dict(state)

    app_state["nlice"] = (
        state.get("nlice_data")
        or _empty_nlice()
    )

    complaint = (
        state.get("complaint") or ""
    ).lower()
    symptom_text = " ".join(
        state.get("associated_symptoms") or []
    ).lower()
    clinical_fields = state.get("clinical_fields") or {}
    complaint_polarity = _symptom_polarity_from_text(complaint)

    # -----------------------------------------------------
    # RULE-BASED EMERGENCY DETECTION
    # -----------------------------------------------------

    EMERGENCY_TERMS = [

        "chest pain",
        "shortness of breath",
        "difficulty breathing",
        "stroke",
        "severe bleeding",
    ]

    emergency_present = False
    for term in EMERGENCY_TERMS:
        canonical = _canonical_symptom_name(term)
        field_name = SYMPTOM_FIELD_NAMES.get(canonical)
        if field_name and clinical_fields.get(field_name) is False:
            continue
        if (
            (field_name and clinical_fields.get(field_name) is True)
            or canonical in symptom_text
            or (
                term in complaint
                and complaint_polarity.get(canonical) is not False
            )
        ):
            emergency_present = True
            break

    if emergency_present:

        urgency = "Emergency"

    else:

        try:

            urgency_result = (
                urgency_classifier_agent(
                    {
                        "complaint": (
                            state.get(
                                "complaint"
                            )
                        ),

                        "nlice": (
                            app_state[
                                "nlice"
                            ]
                        ),
                    }
                )
            )

            urgency = (
                urgency_result.get(
                    "urgency_level",
                    "Low",
                ).title()
            )

        except Exception as exc:

            print(
                "Urgency classifier error:",
                exc,
            )

            urgency = "Low"

    app_state["urgency"] = urgency

    # -----------------------------------------------------
    # CLINICAL CONTEXT
    # -----------------------------------------------------

    try:

        context_result = (
            clinical_context_agent(
                {
                    "complaint": (
                        state.get(
                            "complaint"
                        )
                    ),

                    "nlice": (
                        app_state["nlice"]
                    ),

                    "vision_output": (
                        app_state.get(
                            "vision_output"
                        )
                    ),

                    "safety_flags": urgency,
                }
            )
        )

        clinical_context = (
            context_result.get(
                "clinical_context",
                "Clinical context unavailable.",
            )
        )

    except Exception as exc:

        print(
            "Clinical context error:",
            exc,
        )

        clinical_context = (
            "Clinical context unavailable."
        )

    app_state["clinical_context"] = (
        clinical_context
    )

    summary = summary_agent(app_state)
    normalized_summary = _normalize_clinical_summary(
        state,
        summary,
    )
    app_state["summary"] = normalized_summary
    app_state["recommendations"] = _generate_recommendations(
        {
            **state,
            "urgency": urgency,
        }
    )
    validated_state, validation_warnings = (
        _validate_clinical_state(app_state)
    )

    return {

        "urgency": urgency,

        "clinical_context": (
            clinical_context
        ),

        "summary": normalized_summary,

        "normalized_summary": normalized_summary,

        "recommendations": app_state["recommendations"],

        "validation_warnings": validation_warnings,

        "associated_symptoms": validated_state.get(
            "associated_symptoms",
            state.get("associated_symptoms", []),
        ),

        "step": "done",

        "messages": [
            AIMessage(
                content=(
                    "Thank you. "
                    "Preparing summary for doctor."
                )
            )
        ],
    }


# =========================================================
# FLOW CONTROL
# =========================================================


def should_continue(
    state: ClinicalState,
) -> str:

    if state.get(
        "conversation_complete"
    ):

        return "summary_node"

    if get_missing_workflow_fields(state):
        return "question_node"

    missing = _missing_nlice_fields(
        state.get("nlice_data")
    )

    if missing or not _exploration_is_complete(state):
        return "question_node"

    return "summary_node"


# =========================================================
# BUILD GRAPH
# =========================================================


def build_clinical_graph():

    graph = StateGraph(ClinicalState)

    graph.add_node(
        "extract_info_node",
        extract_info_node,
    )

    graph.add_node(
        "question_node",
        question_node,
    )

    graph.add_node(
        "summary_node",
        summary_node,
    )

    graph.set_entry_point(
        "extract_info_node"
    )

    graph.add_conditional_edges(
        "extract_info_node",
        should_continue,
        {
            "question_node": (
                "question_node"
            ),

            "summary_node": (
                "summary_node"
            ),
        },
    )

    graph.add_edge(
       "question_node",
        END,
    )

    graph.add_edge(
        "summary_node",
        END,
    )

    return graph.compile()


# =========================================================
# CHAT CONTROLLER
# =========================================================


class ChatController:

    def __init__(self):

        self.graph = (
            build_clinical_graph()
        )

        self.state = {

            "step": "intake",

            "messages": [
                AIMessage(
                    content=(
                        "Hello! I am Vitalis, "
                        "your Clinical Assistant. "
                        "What symptoms are you "
                        "experiencing?"
                    )
                )
            ],

            "age_gender": None,
            "complaint": None,
            "duration": None,
            "case_type": None,
            "vision_output": None,
            "lab_report_analysis": {},

            "questions": [],
            "exploration_questions": [],
            "current_question_index": 0,
            "patient_answers": {},
            "associated_symptoms": [],
            "red_flags_screened": False,

            "medications": None,
            "allergies": None,
            "past_history": None,

            "nlice_data": _empty_nlice(),
            "nlice": _empty_nlice(),

            "urgency": None,
            "clinical_context": None,
            "summary": None,
            "normalized_summary": None,
            "recommendations": [],
            "validation_warnings": [],

            # NEW
            "turn_count": 0,
            "conversation_complete": False,
            "concept_memory": {
                "explored": [],
                "uncertain": [],
            },
            "uncertainty_count": 0,
            "workflow_key": None,
            "clinical_fields": {},
        }

    # =====================================================
    # HANDLE TEXT
    # =====================================================

    def handle_text(
        self,
        user_text: str,
    ):

        user_text = (
            user_text or ""
        ).strip()

        if not user_text:

            return {
                "message": (
                    "Please enter a symptom."
                ),

                "nlice_data": (
                    self.state[
                        "nlice_data"
                    ]
                ),

                "workflow_key": self.state.get("workflow_key"),

                "clinical_fields": self.state.get("clinical_fields", {}),
            }

        self.state["turn_count"] += 1

        self.state["messages"].append(
            HumanMessage(content=user_text)
        )

        next_state = self.graph.invoke(
            self.state
        )

        self.state.update(next_state)

        self.state["nlice"] = (
            self.state.get("nlice_data")
            or _empty_nlice()
        )

        validated_state, validation_warnings = (
            _validate_clinical_state(self.state)
        )
        self.state["associated_symptoms"] = (
            validated_state.get(
                "associated_symptoms",
                self.state.get("associated_symptoms", []),
            )
        )
        self.state["validation_warnings"] = validation_warnings
        self.state["recommendations"] = (
            _generate_recommendations(self.state)
        )
        self.state["normalized_summary"] = (
            _normalize_clinical_summary(
                self.state,
                self.state.get("summary"),
            )
        )

        last_message = (
            self.state.get(
                "messages",
                [],
            )[-1]
        )

        return {

            "message": str(
                getattr(
                    last_message,
                    "content",
                    last_message,
                )
            ),

            "nlice_data": (
                self.state.get(
                    "nlice_data"
                )
            ),

            "associated_symptoms": (
                self.state.get(
                    "associated_symptoms",
                    [],
                )
            ),

            "summary": (
                self.state.get("normalized_summary")
            ),

            "recommendations": (
                self.state.get("recommendations", [])
            ),

            "validation_warnings": (
                self.state.get("validation_warnings", [])
            ),

            "concept_memory": (
                self.state.get("concept_memory", {})
            ),

            "workflow_key": (
                self.state.get("workflow_key")
            ),

            "clinical_fields": (
                self.state.get("clinical_fields", {})
            ),

            "uncertainty_count": (
                self.state.get("uncertainty_count", 0)
            ),

            "clinical_analysis": {

                "urgency": (
                    self.state.get(
                        "urgency",
                        "Low",
                    )
                ),

                "score": (
                    self.state.get(
                        "urgency_score",
                        0,
                    )
                ),
            },

            "is_complete": (
                self.state.get("step")
                == "done"
            ),
        }

    # =====================================================
    # HANDLE FILE
    # =====================================================

    def handle_file(
        self,
        image_bytes: bytes,
    ):

        self.state["vision_output"] = vision_reader_agent(image_bytes)
        self.state["lab_report_analysis"] = _extract_lab_report_values(
            self.state["vision_output"]
        )

        return {
            "message": "Medical report uploaded and analyzed.",
            "vision_output": self.state["vision_output"],
            "lab_report_analysis": self.state["lab_report_analysis"],
        }

    # =====================================================
    # GENERATE SUMMARY
    # =====================================================

    def generate_summary(self):

        if not self.state.get("summary"):

            next_state = summary_node(
                self.state
            )

            self.state.update(next_state)

            self.state["nlice"] = (
                self.state.get(
                    "nlice_data"
                )
                or _empty_nlice()
            )

        self.state["step"] = "done"

        return self.state["summary"]
