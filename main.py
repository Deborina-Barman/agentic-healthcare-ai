from __future__ import annotations

import logging
import os
from pathlib import Path
import re
import tempfile
from threading import RLock
from typing import Any

from fastapi import FastAPI, File, Form, Request, UploadFile
from voice_service import transcribe_audio
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from chat_controller import ChatController


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("clinical-intelligence-api")

VOICE_CONTENT_TYPE_SUFFIXES = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/opus": ".opus",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/wav": ".wav",
    "audio/wave": ".wav",
}


def _audio_suffix(upload: UploadFile) -> str:
    content_type = (upload.content_type or "").split(";")[0].strip().lower()
    if content_type in VOICE_CONTENT_TYPE_SUFFIXES:
        return VOICE_CONTENT_TYPE_SUFFIXES[content_type]

    filename_suffix = Path(upload.filename or "").suffix.lower()
    if filename_suffix in {".webm", ".ogg", ".opus", ".mp3", ".m4a", ".mp4", ".wav"}:
        return filename_suffix

    return ".webm"


app = FastAPI(
    title="Clinical Intelligence Dashboard API",
    description="FastAPI bridge between the LangGraph clinical controller and the React dashboard.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


controller = ChatController()
controller_lock = RLock()


class ChatRequest(BaseModel):
    user_input: str = Field(..., min_length=1)
    session_id: str | None = None


def _empty_nlice() -> dict[str, Any]:
    return {
        "nature": "",
        "location": "",
        "intensity": "",
        "chronology": "",
        "excitation": "",
    }


SYMPTOM_FIELD_LABELS = {
    "breathing_difficulty": "breathing difficulty",
    "shortness_of_breath": "breathing difficulty",
    "chest_pain": "chest pain",
    "vomiting": "vomiting",
    "diarrhea": "diarrhea",
    "rash": "rash",
    "confusion": "confusion",
    "cough": "cough",
    "weakness": "weakness",
    "chills": "chills",
    "body_aches": "body aches",
    "sweating": "sweating",
    "dizziness": "dizziness",
    "fainting": "fainting",
}


def _canonical_symptom(symptom: Any) -> str:
    normalized = str(symptom or "").strip().lower()
    aliases = {
        "difficulty breathing": "breathing difficulty",
        "shortness of breath": "breathing difficulty",
        "trouble breathing": "breathing difficulty",
        "chest pressure": "chest pain",
        "vomit": "vomiting",
        "persistent vomiting": "vomiting",
        "severe weakness": "weakness",
        "body ache": "body aches",
        "body pain": "body aches",
    }
    return aliases.get(normalized, normalized)


def _list_value(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item or "").strip()]
    return [
        item.strip()
        for item in re.split(r",|;|\n", str(value))
        if item.strip()
    ]


def _negative_symptoms_from_fields(clinical_fields: dict[str, Any]) -> set[str]:
    return {
        _canonical_symptom(label)
        for field, label in SYMPTOM_FIELD_LABELS.items()
        if clinical_fields.get(field) is False
    }


def _positive_symptoms(symptoms: Any, clinical_fields: dict[str, Any]) -> list[str]:
    denied = _negative_symptoms_from_fields(clinical_fields)
    seen: set[str] = set()
    result: list[str] = []

    for symptom in _list_value(symptoms):
        canonical = _canonical_symptom(symptom)
        if not canonical or canonical in denied or canonical in seen:
            continue
        seen.add(canonical)
        result.append(canonical)

    return result


def _positive_text(payload: dict[str, Any], state: dict[str, Any], nlice: dict[str, Any]) -> str:
    clinical_fields = payload.get("clinical_fields") or state.get("clinical_fields") or {}
    symptoms = _positive_symptoms(
        payload.get("associated_symptoms") or state.get("associated_symptoms") or [],
        clinical_fields,
    )
    positive_field_terms = [
        label
        for field, label in SYMPTOM_FIELD_LABELS.items()
        if clinical_fields.get(field) is True
    ]
    parts = [
        payload.get("complaint") or state.get("complaint"),
        nlice.get("nature"),
        nlice.get("chronology"),
        nlice.get("intensity"),
        clinical_fields.get("temperature_max"),
        *symptoms,
        *positive_field_terms,
    ]
    return " ".join(str(part) for part in parts if part).lower()


def _normalize_analysis(payload: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    raw_analysis = payload.get("clinical_analysis") or state.get("clinical_analysis") or {}

    urgency = (
        raw_analysis.get("urgency")
        or raw_analysis.get("urgency_label")
        or state.get("urgency")
        or "Low"
    )
    score = raw_analysis.get("score", raw_analysis.get("urgency_score", 0))
    reason = raw_analysis.get("reason") or raw_analysis.get("triage_reasoning") or ""

    try:
        score = int(score)
    except (TypeError, ValueError):
        score = 0

    current_nlice = payload.get("nlice_data") or state.get("nlice_data") or state.get("nlice") or _empty_nlice()
    clinical_fields = payload.get("clinical_fields") or state.get("clinical_fields") or {}
    text = _positive_text(payload, state, current_nlice)
    temp_match = re.search(r"\b(9[5-9]|10[0-9]|11[0-5])(?:\.\d+)?\s*(?:f|fahrenheit)?\b", text)
    temp = float(temp_match.group(0).lower().replace("fahrenheit", "").replace("f", "").strip()) if temp_match else 0
    rule_score = 0
    reasons: list[str] = []

    if temp >= 105:
        rule_score += 6
        reasons.append(f"Very high fever: {temp:g} F")
    elif temp > 103:
        rule_score += 5
        reasons.append(f"High fever: {temp:g} F")
    elif temp >= 100.4:
        rule_score += 2

    if any(term in text for term in ["weakness", "fatigue", "chills", "body ache", "body aches", "sweating"]):
        rule_score += 1
        reasons.append("Systemic symptoms reported")
    if any(term in text for term in ["cough", "breath", "shortness of breath", "wheez"]):
        rule_score += 1
        reasons.append("Respiratory symptom reported")
    if any(term in text for term in ["vomit", "diarrhea"]):
        rule_score += 2 if temp > 103 else 1
        reasons.append("Fluid loss symptom reported")
    if "chest pain" in text and clinical_fields.get("chest_pain") is not False:
        rule_score += 5
        reasons.append("Chest pain reported")

    score = max(score, min(10, rule_score))
    if score >= 8:
        urgency = "Urgent"
    elif score >= 6:
        urgency = "High"
    elif score >= 3:
        urgency = "Moderate"
    else:
        urgency = "Low"
    if reasons:
        reason = "; ".join(dict.fromkeys(item for item in [*reasons, reason] if item).keys())

    return {
        "urgency": str(urgency).title(),
        "score": max(0, min(10, score)),
        "reason": str(reason),
    }


def _text_blob(*values: Any) -> str:
    parts: list[str] = []
    for value in values:
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
        elif isinstance(value, dict):
            parts.extend(str(item) for item in value.values())
        elif value:
            parts.append(str(value))
    return " ".join(parts).lower()


def _classify_clinical_category(payload: dict[str, Any], state: dict[str, Any], nlice: dict[str, Any]) -> str:
    clinical_fields = payload.get("clinical_fields") or state.get("clinical_fields") or {}
    text = _positive_text(payload, state, nlice)

    has_fever = "fever" in text or "temperature" in text
    has_vomiting = ("vomit" in text or "nausea" in text or "diarrhea" in text) and not (
        clinical_fields.get("vomiting") is False and clinical_fields.get("diarrhea") is False
    )
    has_chest_pain = ("chest pain" in text or "pressure" in text or "sweating" in text) and clinical_fields.get("chest_pain") is not False
    has_breathing = ("breath" in text or "shortness of breath" in text or "wheez" in text or "cough" in text) and not (
        clinical_fields.get("breathing_difficulty") is False and clinical_fields.get("cough") is False
    )
    has_neuro = any(term in text for term in ["confusion", "fainting", "seizure", "weakness", "stroke", "dizziness"]) and not (
        clinical_fields.get("confusion") is False and clinical_fields.get("weakness") is False
    )
    has_pregnancy = any(term in text for term in ["pregnan", "missed period", "vaginal bleeding"])

    if has_chest_pain:
        return "cardiac"
    if has_breathing:
        return "respiratory"
    if has_neuro:
        return "neurology"
    if has_pregnancy:
        return "pregnancy"
    if has_fever and has_vomiting:
        return "infectious_gi"
    if has_fever:
        return "infectious"
    if has_vomiting:
        return "gastrointestinal"
    return "general"


def _select_active_modules(category: str, payload: dict[str, Any], state: dict[str, Any], nlice: dict[str, Any]) -> list[str]:
    base_modules = [
        "GeneralSnapshotCard",
        "TriageAlertsCard",
        "ClinicalCompletenessCard",
        "AIClinicalSummaryCard",
    ]

    category_modules = {
        "infectious": ["FeverClinicalCard", "MedicationCard"],
        "infectious_gi": ["FeverClinicalCard", "GastrointestinalCard", "HydrationRiskCard", "MedicationCard"],
        "gastrointestinal": ["GastrointestinalCard", "HydrationRiskCard", "MedicationCard"],
        "cardiac": ["CardiacRiskCard", "RespiratoryRiskCard", "MedicationCard"],
        "respiratory": ["RespiratoryRiskCard", "CardiacRiskCard", "MedicationCard"],
        "neurology": ["NeurologyRiskCard", "MedicationCard"],
        "pregnancy": ["PregnancyRiskCard", "MedicationCard"],
        "general": ["MedicationCard"],
    }

    modules = [*base_modules, *category_modules.get(category, category_modules["general"]), "LabReportAnalysisCard", "TimelineCard", "RecommendedNextStepsCard", "ActionPanel"]
    clinical_fields = payload.get("clinical_fields") or state.get("clinical_fields") or {}
    text = _positive_text(payload, state, nlice)

    if ("pregnan" in text or "missed period" in text) and "PregnancyRiskCard" not in modules:
        modules.insert(-3, "PregnancyRiskCard")
    if ("confusion" in text or "fainting" in text or "seizure" in text) and clinical_fields.get("confusion") is not False and "NeurologyRiskCard" not in modules:
        modules.insert(-3, "NeurologyRiskCard")
    if ("fever" in text or "temperature" in text) and "FeverClinicalCard" not in modules:
        modules.insert(-3, "FeverClinicalCard")
    if ("cough" in text or "breath" in text or "shortness of breath" in text) and not (
        clinical_fields.get("breathing_difficulty") is False and clinical_fields.get("cough") is False
    ) and "RespiratoryRiskCard" not in modules:
        modules.insert(-3, "RespiratoryRiskCard")
    if ("abdominal" in text or "stomach" in text or "vomit" in text or "diarrhea" in text) and not (
        clinical_fields.get("vomiting") is False and clinical_fields.get("diarrhea") is False
    ) and "GastrointestinalCard" not in modules:
        modules.insert(-3, "GastrointestinalCard")
    if ("abdominal" in text or "stomach" in text or "vomit" in text or "diarrhea" in text) and not (
        clinical_fields.get("vomiting") is False and clinical_fields.get("diarrhea") is False
    ) and "HydrationRiskCard" not in modules:
        modules.insert(-3, "HydrationRiskCard")

    deduped: list[str] = []
    for module in modules:
        if module not in deduped:
            deduped.append(module)
    return deduped

def _unified_response(payload: dict[str, Any] | str | None = None) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {"message": payload or ""}
    state = dict(controller.state)

    current_nlice = payload.get("nlice_data") or state.get("nlice_data") or state.get("nlice") or _empty_nlice()
    clinical_fields = payload.get("clinical_fields") or state.get("clinical_fields") or {}
    associated_symptoms = _positive_symptoms(
        payload.get("associated_symptoms") or state.get("associated_symptoms") or [],
        clinical_fields,
    )
    payload = {
        **payload,
        "associated_symptoms": associated_symptoms,
        "clinical_fields": clinical_fields,
        "medication_taken": clinical_fields.get("medication_name"),
        "medication_response": clinical_fields.get("medication_response"),
    }
    state = {
        **state,
        "associated_symptoms": associated_symptoms,
        "clinical_fields": clinical_fields,
    }
    current_analysis = _normalize_analysis(payload, state)
    clinical_category = _classify_clinical_category(payload, state, current_nlice)
    active_modules = _select_active_modules(clinical_category, payload, state, current_nlice)

    return {
        "status": "success",
        "data": {
            "message": payload.get("message") or "",
            "complaint": payload.get("complaint") or state.get("complaint") or current_nlice.get("nature") or "",
            "duration": payload.get("duration") or state.get("duration") or current_nlice.get("chronology") or "",
            "medications": payload.get("medications") or state.get("medications") or "",
            "medication_taken": payload.get("medication_taken") or clinical_fields.get("medication_name"),
            "medication_response": payload.get("medication_response") or clinical_fields.get("medication_response"),
            "associated_symptoms": associated_symptoms,
            "clinical_context": payload.get("clinical_context") or state.get("clinical_context") or "",
            "summary": payload.get("summary") or state.get("normalized_summary") or state.get("summary") or "",
            "normalized_summary": payload.get("normalized_summary") or state.get("normalized_summary") or "",
            "recommendations": payload.get("recommendations") or state.get("recommendations") or [],
            "validation_warnings": payload.get("validation_warnings") or state.get("validation_warnings") or [],
            "concept_memory": payload.get("concept_memory") or state.get("concept_memory") or {},
            "workflow_key": payload.get("workflow_key") or state.get("workflow_key") or "",
            "clinical_fields": clinical_fields,
            "vision_output": payload.get("vision_output") or state.get("vision_output"),
            "lab_report_analysis": payload.get("lab_report_analysis") or state.get("lab_report_analysis") or {},
            "uncertainty_count": payload.get("uncertainty_count") or state.get("uncertainty_count") or 0,
            "urgency": current_analysis["urgency"],
            "urgency_score": current_analysis["score"],
            "clinical_category": clinical_category,
            "active_modules": active_modules,
            "nlice_data": current_nlice,
            "clinical_analysis": current_analysis,
            "is_complete": bool(payload.get("is_complete", state.get("is_complete", False))),
            "step": payload.get("step") or state.get("step") or "intake",
        },
    }

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled API error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "Clinical intelligence service failed. Please retry or start a new session.",
            "detail": str(exc),
        },
    )


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat")
def chat(request: ChatRequest) -> dict[str, Any]:
    user_input = request.user_input.strip()
    logger.info("Processing chat turn session_id=%s", request.session_id or "default")

    with controller_lock:
        payload = controller.handle_text(user_input)
        return _unified_response(payload)


@app.post("/upload")
async def upload(file: UploadFile = File(...)) -> dict[str, Any]:
    logger.info("Processing upload filename=%s content_type=%s", file.filename, file.content_type)
    temp_path = None

    try:
        file_bytes = await file.read()
        suffix = os.path.splitext(file.filename or "")[1]

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(file_bytes)
            temp_path = temp_file.name

        with controller_lock:
            payload = controller.handle_file(file_bytes)
            return _unified_response(payload)
    finally:
        await file.close()
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                logger.warning("Could not remove temporary upload file: %s", temp_path)
                
@app.post("/voice")
async def voice_chat(
    audio: UploadFile = File(...),
    language: str | None = Form(None),
):

    logger.info(
        "Processing voice input: %s",
        audio.filename,
    )

    temp_path = None

    try:

        # -----------------------------------
        # SAVE TEMP AUDIO FILE
        # -----------------------------------

        content = await audio.read()

        logger.info(
            "Voice upload metadata: filename=%s content_type=%s bytes=%s selected_language=%s",
            audio.filename,
            audio.content_type,
            len(content),
            language or "auto",
        )

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=_audio_suffix(audio)
        ) as temp_audio:

            temp_audio.write(content)

            temp_path = temp_audio.name

        # -----------------------------------
        # TRANSCRIBE AUDIO
        # -----------------------------------

        transcription = transcribe_audio(
            temp_path,
            language=language,
        )

        logger.info(
            "Voice transcription: %s",
            transcription,
        )

        return {
            "status": "success",
            "transcription": transcription,
        }

    except Exception as exc:

        logger.exception(
            "Voice processing failed"
        )

        return {
            "status": "error",
            "message": str(exc),
        }

    finally:

        await audio.close()

        if (
            temp_path
            and os.path.exists(temp_path)
        ):

            try:

                os.remove(temp_path)

            except OSError:

                logger.warning(
                    "Could not remove temp audio file"
                )

@app.get("/summary")
def summary() -> dict[str, Any]:
    logger.info("Generating final clinical summary")

    with controller_lock:
        payload = controller.generate_summary()
        unified = _unified_response(payload)
        unified["data"]["summary"] = (
            payload.get("summary")
            if isinstance(payload, dict)
            else controller.state.get("summary")
        )
        return unified

@app.post("/reset")
async def reset():
    global controller
    # 1. Purana controller delete karke naya banao
    controller = ChatController() 
    
    # 2. Counter aur State ko explicitly clean karo
    controller.state["ask_count"] = 0
    controller.state["step"] = "intake"
    controller.state["nlice_data"] = _empty_nlice()
    
    print("DEBUG: SevaCare AI is now fully reset and ready for the next patient!")
    return {"status": "success", "message": "System Reset Successful"}
if __name__ == "__main__":
    import uvicorn
    # Ye line server ko chalu rakhti hai
    uvicorn.run(app, host="127.0.0.1", port=8000)
