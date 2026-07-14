# SevaCare AI Architecture

Developer-focused architecture documentation based on the current repository state.

![Active SevaCare AI architecture](docs/images/architecture.svg)

The diagram above reflects the active React + FastAPI path. For the concise recruiter-facing view, see the [README architecture section](README.md#system-architecture).

## 1. Project Overview

SevaCare AI is an AI-assisted clinical intake and triage prototype. It collects patient symptom history through a conversational workflow, structures the symptom pattern into NLICE fields, generates contextual follow-up questions, classifies urgency, and renders a doctor-facing dashboard with summaries, timeline, alerts, and export support.

The active application path is:

```text
React frontend (`frontend/src/App.js`)
  -> FastAPI backend (`main.py`)
  -> ChatController (`chat_controller.py`)
  -> LangGraph workflow
  -> Gemini agents + FAISS retrievers + rule-based clinical state logic
  -> unified API response
  -> adaptive dashboard state (`clinicalState.js`, `AdaptiveDashboard.js`)
```

The repository also contains earlier/legacy interfaces:

- `app_streamlit.py` and `updated_app_streamlit.py`: Streamlit intake UI versions.
- Root `App.js` and root `DashboardComponents.js`: older React dashboard/intake components outside the active `frontend/` app.

### Problem Statement

General chatbots can answer medical questions, but clinical intake needs structured history collection, consistency, safety boundaries, triage handoff, and clinician-readable output. SevaCare AI addresses this by separating workflow control from LLM phrasing:

- deterministic state tracking decides what information is missing;
- retrieval and Gemini improve the quality of follow-up phrasing;
- rule-based and ML components produce urgency signals;
- the frontend turns state into a dashboard rather than a plain chat transcript.

### End-to-End Workflow

```text
Patient starts session
  -> enters patient metadata in React modal
  -> types or records symptom
  -> FastAPI /chat receives text
  -> ChatController appends HumanMessage
  -> LangGraph invokes extract_info_node
  -> state updates: NLICE, associated symptoms, medications, concept memory
  -> should_continue routes to question_node or summary_node
  -> question_node selects priority/exploration/NLICE question
  -> optional FAISS retrieval + Gemini question generation
  -> response returned to React
  -> frontend syncClinicalState derives dashboard fields and triage score
  -> repeat until intake completes
  -> summary_node generates urgency, clinical context, normalized summary, recommendations
  -> dashboard can export report as PDF
```

## 2. System Architecture

### High-Level Architecture

```text
┌─────────────────────────────────────────────────────────────────────┐
│                         Browser / React UI                          │
│ frontend/src/App.js                                                  │
│ - patient modal                                                      │
│ - chat interface                                                     │
│ - MediaRecorder voice capture                                        │
│ - adaptive dashboard                                                 │
│ - local visit history                                                │
│ - PDF export                                                         │
└───────────────┬───────────────────────────────────────┬─────────────┘
                │ /chat, /summary, /reset                │ /voice
                ▼                                        ▼
┌─────────────────────────────────────┐     ┌─────────────────────────┐
│ FastAPI API (`main.py`)              │     │ Voice service            │
│ - CORS                               │     │ `voice_service.py`       │
│ - request/response normalization     │     │ - Faster Whisper small   │
│ - dashboard module selection         │     │ - en/hi/bn language hint │
│ - endpoint orchestration             │     │ - transcript cleanup     │
└──────────────────┬──────────────────┘     └─────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│ ChatController + LangGraph (`chat_controller.py`)                    │
│ StateGraph: extract_info_node -> question_node OR summary_node -> END │
│ - deterministic NLICE extraction                                     │
│ - concept memory and duplicate avoidance                             │
│ - priority clinical follow-up rules                                  │
│ - summary generation and urgency routing                             │
└───────────────┬──────────────────────────┬──────────────────────────┘
                │                          │
                ▼                          ▼
┌───────────────────────────┐   ┌─────────────────────────────────────┐
│ Gemini agents              │   │ Retrieval resources                  │
│ - followup_question_agent  │   │ - followup_q FAISS examples          │
│ - clinical_exploration     │   │ - SymCAT FAISS docs                  │
│ - clinical_context         │   │ - all-MiniLM-L6-v2 embeddings        │
│ - reader/vision            │   │ - cached SentenceTransformer models │
└───────────────────────────┘   └─────────────────────────────────────┘
```

### Frontend Architecture

The active frontend is the Create React App in `frontend/`.

```text
frontend/src/index.js
  -> frontend/src/App.js
      -> AdaptiveClinicalDashboard
          -> dashboardConfig.js
              -> DashboardComponents.js
              -> ClinicalModules.js
      -> clinicalState.js
```

Key responsibilities:

- `App.js`: top-level UI state, chat calls, voice recording, patient modal, visit history, PDF export, backend reset.
- `clinicalState.js`: transforms backend packets plus latest user turn into a richer dashboard model.
- `AdaptiveDashboard.js`: renders the patient card and active dashboard modules.
- `dashboardConfig.js`: maps clinical categories and module names to React components.
- `DashboardComponents.js`: general dashboard cards.
- `ClinicalModules.js`: category-specific cards for fever, cardiac, respiratory, GI, hydration, neurology, pregnancy, and medication review.

The frontend calculates its own `triage_score`, `triage_level`, red flags, timeline, summary, and active modules after receiving backend data. This is useful for responsive dashboard behavior but creates duplicated clinical logic with `main.py` and `chat_controller.py`.

### Backend Architecture

`main.py` is the FastAPI bridge between React and the clinical controller.

Endpoints:

- `GET /health`: health check.
- `POST /chat`: accepts `ChatRequest(user_input, session_id)` and returns a unified dashboard response.
- `POST /upload`: accepts image file bytes, passes them to `controller.handle_file()`.
- `POST /voice`: accepts browser audio, runs Faster Whisper, returns transcript only.
- `GET /summary`: forces summary generation.
- `POST /reset`: creates a new `ChatController` and resets core state.

Backend response normalization:

- `_unified_response()` reads controller state and payload.
- `_normalize_analysis()` applies additional rule-based triage scoring.
- `_classify_clinical_category()` maps text to general/cardiac/respiratory/etc.
- `_select_active_modules()` chooses dashboard cards.

The backend has a single global `ChatController` guarded by `RLock`, so the active implementation behaves as one shared session unless expanded to per-session controller storage.

### LangGraph Architecture

The graph is built in `build_clinical_graph()`:

```text
Entry: extract_info_node

extract_info_node
  -> should_continue(state)
       ├─ question_node -> END
       └─ summary_node  -> END
```

Each `/chat` request invokes the graph once. The graph returns after either one assistant question or one summary node result. Conversation continuity is held in `ChatController.state`.

### RAG Architecture

There are two retrieval systems.

1. Follow-up question retrieval:

```text
data/followup_q/train-00000-of-00001.parquet
  -> build_followup_index.py
  -> data/followup_q/followup_index.faiss
  -> data/followup_q/followup_records.pkl
  -> followup_retriever.py
  -> agents/followup_question_agent.py
  -> agents/clinical_exploration_agent.py
```

This is the active RAG path used by the LangGraph question node.

2. SymCAT retrieval:

```text
data/symcat-801-diseases.csv
  -> rag/process_symcat.py
  -> data/symptom_disease_map.json
  -> rag/build_documents.py
  -> data/symcat_documents.json
  -> rag/build_index.py
  -> data/symcat_index.faiss + data/symcat_docs.pkl
  -> rag/retrieve_context.py
  -> agents/question_agent.py
```

This is used by the older `patient_question_agent()` path, not by the current LangGraph `question_node`.

### Voice Architecture

```text
Browser microphone
  -> navigator.mediaDevices.getUserMedia()
  -> MediaRecorder audio/webm chunks
  -> Blob recording.webm
  -> POST /voice multipart FormData(audio, language)
  -> main.py saves temp audio file
  -> voice_service.transcribe_audio()
  -> faster_whisper.decode_audio()
  -> WhisperModel("small", cpu, int8).transcribe()
  -> cleaned transcript returned to frontend
  -> frontend places transcript into input box
  -> user sends it through normal /chat flow
```

Supported backend language hints are `en`, `hi`, and `bn`. The frontend modal offers Hindi, English, Tamil, Telugu, and Bengali, but unsupported languages fall back to Whisper auto-detection because `_normalize_language()` only allows `en`, `hi`, and `bn`.

### Dashboard Architecture

```text
Backend payload
  -> syncClinicalState(previousState, backendPayload, turnContext)
       -> parse temperature, severity, duration
       -> detect symptoms, negatives, breathing difficulty, medications
       -> scoreClinicalUrgency()
       -> classifyClinicalCategory()
       -> active_modules
       -> deriveTimeline()
       -> generateClinicalSummary()
  -> AdaptiveClinicalDashboard
       -> PatientInformationCard
       -> active module cards
```

The dashboard is adaptive: `clinical_category` and `active_modules` determine which cards are rendered.

## 3. File-by-File Documentation

### `main.py`

Purpose: FastAPI backend entry point and response normalizer.

Inputs: JSON chat requests, image uploads, voice uploads, summary/reset requests.

Outputs: unified JSON responses for frontend dashboard, transcript responses, health status.

Dependencies: `fastapi`, `pydantic`, `voice_service.transcribe_audio`, `ChatController`, `CORSMiddleware`, `tempfile`, `RLock`.

Key functions/classes:

- `ChatRequest`: Pydantic request model.
- `_audio_suffix()`: chooses temp file suffix from MIME type or filename.
- `_empty_nlice()`: returns blank NLICE object.
- `_normalize_analysis()`: combines controller analysis with rule-based scoring.
- `_classify_clinical_category()`: maps complaint/symptom text to dashboard category.
- `_select_active_modules()`: selects dashboard cards.
- `_unified_response()`: normalizes controller output for React.
- `chat()`, `upload()`, `voice_chat()`, `summary()`, `reset()`: API endpoints.

Interactions:

- Owns a global `controller = ChatController()`.
- Calls `controller.handle_text()`, `controller.handle_file()`, and `controller.generate_summary()`.
- Calls `transcribe_audio()` for `/voice`.
- Supplies `clinical_category` and `active_modules` consumed by `frontend/src/clinicalState.js`.

### `chat_controller.py`

Purpose: Main clinical conversation orchestrator and LangGraph workflow implementation.

Inputs: patient text, image bytes through `handle_file()`, current state.

Outputs: assistant questions, updated NLICE state, summary, clinical context, urgency, recommendations.

Dependencies: `langgraph`, `langchain_core.messages`, Gemini client, `clinical_context_agent`, `clinical_exploration_agent`, `followup_question_agent`, `vision_reader_agent`, `summary_agent`, `urgency_classifier_agent`.

Key classes:

- `ClinicalState`: TypedDict state contract for graph.
- `ChatController`: long-lived controller holding graph and conversation state.

Key functions:

- State helpers: `_empty_nlice()`, `_missing_nlice_fields()`, `_latest_user_message()`, `_latest_ai_message()`.
- Extraction helpers: `_extract_associated_symptoms()`, `_normalize_contextual_reply()`, `_json_from_text()`.
- Memory/redundancy helpers: `_update_concept_memory()`, `_semantic_similarity()`, `_is_semantically_redundant_question()`.
- Question routing: `_priority_followup_questions()`, `_select_question_focus()`, `_exploration_is_complete()`.
- Summary/triage helpers: `_normalize_clinical_summary()`, `_generate_recommendations()`, `_validate_clinical_state()`.
- LangGraph nodes: `extract_info_node()`, `question_node()`, `summary_node()`.
- Routing: `should_continue()`.
- Graph builder: `build_clinical_graph()`.
- Controller methods: `handle_text()`, `handle_file()`, `generate_summary()`.

Interactions:

- `main.py` is the primary caller.
- `question_node()` calls `clinical_exploration_agent()` for exploration questions and `followup_question_agent()` for NLICE-targeted questions.
- `summary_node()` calls `urgency_classifier_agent()`, `clinical_context_agent()`, and `summary_agent()`.
- `handle_file()` calls `vision_reader_agent()` and stores `vision_output`.

### `voice_service.py`

Purpose: Local audio transcription service.

Inputs: path to temporary audio file, optional language code.

Outputs: cleaned transcript string or empty string for too-short/suspicious audio.

Dependencies: `faster_whisper.WhisperModel`, `faster_whisper.audio.decode_audio`, `logging`, `re`.

Key functions:

- `_normalize_language()`: allows `en`, `hi`, `bn`; otherwise auto-detect.
- `_clean_transcript()`: trims whitespace and repeated punctuation.
- `_mean_metric()`: averages Whisper diagnostics.
- `transcribe_audio()`: decodes audio, validates duration, transcribes, logs segment metrics, filters suspicious transcript patterns.

Interactions:

- Called only by `main.py` `/voice`.
- Its transcript is not automatically sent to the clinical graph; frontend places it in the input box for user submission.

### `agents/followup_question_agent.py`

Purpose: Retrieval-augmented Gemini agent for one NLICE-targeted follow-up question.

Inputs: complaint, NLICE state, target field, associated symptoms, previous questions, conversation context, `top_k`.

Outputs: `FollowupQuestionResult` with question, source, error, retrieved examples.

Dependencies: Gemini `google.genai`, `followup_retriever.retrieve_followup_examples`.

Key functions/classes:

- `FollowupQuestionResult`: TypedDict output shape.
- `_first_missing_field()`, `_retrieval_query()`, `_format_nlice_state()`, `_format_retrieved_examples()`.
- `_target_field_guidance()`: per-NLICE prompt guidance.
- `_build_retrieval_prompt()`: prompt that binds Gemini to deterministic target field.
- `_clean_question()`, `_is_generic_question()`.
- `followup_question_agent()`: retrieval + Gemini + fallback.
- `_fallback_question()`: deterministic fallback map.

Interactions:

- Called by `chat_controller.question_node()` when mode is `nlice`.
- Uses `followup_retriever.py` for clinician example retrieval.

### `agents/clinical_exploration_agent.py`

Purpose: Retrieval-augmented Gemini agent for non-NLICE exploration questions such as associated symptoms, red flags, and contextual follow-ups.

Inputs: complaint, focus, NLICE state, associated symptoms, missing fields, previous questions, recent conversation.

Outputs: `ClinicalExplorationResult` with question, focus, source, error, retrieved examples.

Dependencies: Gemini, `retrieve_followup_examples`.

Key functions/classes:

- `ClinicalExplorationResult`: TypedDict result.
- `FOCUS_GUIDANCE`: focus-specific instructions.
- `_build_exploration_prompt()`: prompt for clinician-style exploration.
- `_fallback_question()`: deterministic focus-specific fallback.
- `clinical_exploration_agent()`: retrieval + Gemini + fallback.

Interactions:

- Called by `chat_controller.question_node()` when mode is `exploration`.

### `followup_retriever.py`

Purpose: Load and query the Followup-Q FAISS index.

Inputs: patient complaint string, `top_k`.

Outputs: examples containing original patient message, clinician questions, EHR text, and L2 distance.

Dependencies: `faiss`, `numpy`, `sentence_transformers.SentenceTransformer`, `pickle`.

Key classes/functions:

- `FollowupExample`, `RetrievalResult`: TypedDict contracts.
- `_load_index()`, `_load_records()`, `_load_model()`: lazy cached loaders.
- `retrieve_followup_examples()`: embeds query and searches FAISS.
- `get_retriever_stats()`: debugging stats.

Interactions:

- Called by both follow-up agents.
- Reads `data/followup_q/followup_index.faiss` and `followup_records.pkl`.

Important note: paths are hardcoded to `C:\Users\debor\OneDrive\Desktop\agentic_healthcare_ai\data\followup_q`, unlike the SymCAT retriever which uses relative paths.

### `build_followup_index.py`

Purpose: Build FAISS index and pickled records from the Followup-Q parquet dataset.

Inputs: `data/followup_q/train-00000-of-00001.parquet`.

Outputs: `followup_index.faiss`, `followup_records.pkl`.

Dependencies: `pandas`, `faiss`, `numpy`, `sentence_transformers`.

Interactions:

- Produces assets consumed by `followup_retriever.py`.

Important note: uses hardcoded absolute paths.

### `rag/process_symcat.py`

Purpose: Convert SymCAT disease CSV into symptom-to-disease JSON.

Inputs: `data/symcat-801-diseases.csv`.

Outputs: `data/symptom_disease_map.json` when `--output` is provided.

Dependencies: `csv`, `json`, `argparse`.

Key functions: `_candidate_disease_columns()`, `build_symptom_disease_map()`, `main()`.

Interactions:

- First step of the SymCAT RAG pipeline.

### `rag/build_documents.py`

Purpose: Convert symptom-disease map into embedding-ready text documents.

Inputs: `data/symptom_disease_map.json`.

Outputs: `data/symcat_documents.json`.

Dependencies: `json`, `argparse`.

Key functions: `load_symptom_disease_map()`, `build_document()`, `build_documents()`, `main()`.

Interactions:

- Produces documents for `rag/build_index.py`.

### `rag/build_index.py`

Purpose: Embed SymCAT documents and build FAISS index.

Inputs: `data/symcat_documents.json`.

Outputs: `data/symcat_index.faiss`, `data/symcat_docs.pkl`.

Dependencies: `faiss`, `numpy`, `SentenceTransformer`.

Key functions: `load_documents()`, `build_faiss_index()`, `save_outputs()`, `main()`.

Interactions:

- Produces assets consumed by `rag/retrieve_context.py`.

### `rag/retrieve_context.py`

Purpose: Runtime retriever for SymCAT context.

Inputs: query string and `k`.

Outputs: list of matching document strings.

Dependencies: `faiss`, `pickle`, `SentenceTransformer`.

Key functions: `get_resources()`, `retrieve_context()`.

Interactions:

- Called by `agents/question_agent.py`.
- Not used by the current LangGraph question path.

### `agents/question_agent.py`

Purpose: Older RAG question generator over SymCAT documents.

Inputs: complaint and optional age/gender.

Outputs: dictionary with 3-5 follow-up questions.

Dependencies: Gemini, `rag.retrieve_context.retrieve_context`.

Key functions: `patient_question_agent()`.

Interactions:

- Currently not called by `chat_controller.py`; retained as a supporting/legacy agent.

### `agents/clinical_context_agent.py`

Purpose: Generate non-diagnostic clinical context for a doctor.

Inputs: complaint, vision output, patient answers, safety flags.

Outputs: `{ "clinical_context": text }`.

Dependencies: Gemini.

Key functions: `clinical_context_agent()`.

Interactions:

- Called by `chat_controller.summary_node()`.

### `agents/clinical_synthesis_agent.py`

Purpose: Convert patient-reported information into structured NLICE JSON.

Inputs: complaint, patient answers, age/gender.

Outputs: normalized dictionary with chief complaint, NLICE, associated symptoms, risk flags, clinical summary.

Dependencies: Gemini, JSON parsing.

Key functions: `_normalize_text()`, `_normalize_intensity()`, `_normalize_output()`, `clinical_synthesis_agent()`.

Interactions:

- Present in repo, but not called by the active `chat_controller.py`.

### `agents/complaint_agent.py`

Purpose: Gemini-based complaint organizer.

Inputs: raw patient text.

Outputs: formatted complaint with primary complaint, associated symptoms, duration, severity.

Dependencies: Gemini.

Interactions:

- Present as standalone/legacy support; not used in active graph.

### `agents/reader_agent.py`

Purpose: Prescription/image reader wrapper.

Inputs: image bytes.

Outputs: `vision_output`, low confidence, and confirmation-required flag.

Dependencies: `services.gemini_vision_service.read_prescription_with_gemini`.

Interactions:

- Called by `ChatController.handle_file()`.

### `services/gemini_vision_service.py`

Purpose: Send prescription image bytes to Gemini Vision.

Inputs: image bytes.

Outputs: visible prescription text or `NOT SURE`/error string.

Dependencies: Gemini, `google.genai.types`, `PIL.Image`, `io`.

Key functions: `read_prescription_with_gemini()`.

Interactions:

- Called via `reader_agent.py`.

Important note: MIME type is always sent as `image/jpeg`, regardless of uploaded file type.

### `agents/urgency_classifier_agent.py`

Purpose: Runtime urgency classifier wrapper around saved ML artifacts.

Inputs: state with NLICE fields.

Outputs: `{ "urgency_level": label, "reason": "Based on intensity and symptom pattern" }`.

Dependencies: `joblib`, `ml/model.pkl`, `ml/encoders.pkl`.

Key functions: `load_model_artifacts()`, `_extract_nlice_features()`, `_encode_features()`, `urgency_classifier_agent()`.

Interactions:

- Called by `chat_controller.summary_node()`.

### `ml/urgency_model.py`

Purpose: Train and save synthetic RandomForest urgency classifier.

Inputs: generated synthetic NLICE dataset.

Outputs: `ml/model.pkl`, `ml/encoders.pkl`.

Dependencies: `pandas`, `scikit-learn`, `joblib`.

Key functions: `determine_urgency()`, `generate_synthetic_dataset()`, `preprocess_data()`, `train_and_save_model()`, `predict_urgency()`.

Interactions:

- Produces artifacts used by `agents/urgency_classifier_agent.py`.

### `agents/summary_agent.py`

Purpose: Generate structured SOAP-like non-diagnostic clinical summary.

Inputs: controller state.

Outputs: Markdown string.

Key functions: `summary_agent()`.

Interactions:

- Called by `chat_controller.summary_node()`.
- `chat_controller` then replaces it with a shorter normalized summary for API/dashboard use.

### `agents/safety_agent.py`

Purpose: Basic safety flag extraction from patient answers.

Inputs: `patient_answers` dict.

Outputs: safety flags list.

Interactions:

- Present as support/legacy logic; not called by the active graph.

### `frontend/src/App.js`

Purpose: Active React application shell.

Inputs: user text, microphone audio, patient metadata, backend API responses.

Outputs: chat messages, clinical dashboard state, local history, PDF export.

Dependencies: React hooks, `framer-motion`, `lucide-react`, `jspdf`, `html2canvas`, `AdaptiveClinicalDashboard`, `clinicalState.js`.

Key functions:

- `handleSend()`: POST `/chat`.
- `startRecording()`, `stopRecording()`, `toggleRecording()`: browser voice recording.
- `sendAudioToBackend()`: POST `/voice`.
- `exportPDF()`: render `#report-area` to PDF.
- `resetSession()`: POST `/reset`.
- `initializePatientSession()`: initialize patient info.

Interactions:

- Calls FastAPI at `http://127.0.0.1:8000`.
- Sends backend packets to `syncClinicalState()`.
- Passes state to `AdaptiveClinicalDashboard`.

### `frontend/src/clinicalState.js`

Purpose: Frontend clinical state derivation and dashboard intelligence.

Inputs: previous clinical state, backend payload, latest user text, last assistant question, timestamp.

Outputs: derived clinical state for dashboard cards.

Key functions:

- `createInitialClinicalState()`, `formatVisitTime()`.
- Parsers: `parseTemperature()`, `parseSeverity()`, `parseDuration()`.
- Detection: `detectSymptoms()`, `detectNegativeFindings()`, `detectComplaint()`, `detectBreathingDifficulty()`, `detectMedications()`.
- `scoreClinicalUrgency()`: frontend triage scoring.
- `deriveTimeline()`: event timeline.
- `generateClinicalSummary()`: frontend summary.
- `classifyClinicalCategory()`, `fallbackModulesForCategory()`.
- `syncClinicalState()`: main merge and derivation function.

Interactions:

- Used by `frontend/src/App.js`.
- Duplicates some backend clinical logic.

### `frontend/src/AdaptiveDashboard.js`

Purpose: Render patient info and active dashboard modules.

Inputs: clinical data, messages, export callback, fallback visit time.

Outputs: dashboard JSX.

Dependencies: `PatientInformationCard`, `MODULE_COMPONENTS`, `resolveActiveModules`.

### `frontend/src/dashboardConfig.js`

Purpose: Category-to-module mapping and module resolution.

Inputs: `clinicalData`.

Outputs: ordered module names.

Key exports: `CATEGORY_MODULES`, `MODULE_COMPONENTS`, `resolveActiveModules()`.

### `frontend/src/DashboardComponents.js`

Purpose: General dashboard cards and report-area layout.

Components:

- `ClinicalCard`
- `PatientInformationCard`
- `ClinicalSnapshotCard`
- `TriageAlertsCard`
- `AIClinicalSummaryCard`
- `TimelineCard`
- `RecommendedNextStepsCard`
- `ActionPanel`
- `ClinicalIntelligenceDashboard`

Interactions:

- Used by `AdaptiveDashboard.js` and `dashboardConfig.js`.

### `frontend/src/ClinicalModules.js`

Purpose: Domain-specific dashboard cards.

Components:

- `FeverClinicalCard`
- `CardiacRiskCard`
- `RespiratoryRiskCard`
- `GastrointestinalCard`
- `MedicationCard`
- `HydrationRiskCard`
- `NeurologyRiskCard`
- `PregnancyRiskCard`

### `frontend/package.json`

Purpose: React project dependencies and scripts.

Important dependencies: React 19, React Scripts 5, Framer Motion, Lucide React, html2canvas, jsPDF, Tailwind.

### `requirements.txt`

Purpose: Backend dependency list.

Currently includes: `google-genai`, `langgraph`, `langchain-core`, `python-dotenv`, `pillow`, `pandas`, `scikit-learn`, `joblib`, `fastapi`, `uvicorn`, `python-multipart`.

Important gap: active code imports packages not listed here, including `faster-whisper`, `faiss`, `sentence-transformers`, `numpy`, `streamlit`, and PDF dependencies for Streamlit versions.

### `app_streamlit.py` and `updated_app_streamlit.py`

Purpose: Earlier Streamlit UIs for clinical intake.

Inputs: Streamlit form/chat input, file upload.

Outputs: Streamlit chat/report interface and PDF download.

Dependencies: `streamlit`, `ChatController`, PDF generation helpers.

Interactions:

- Use the same `ChatController` but are separate from the active React/FastAPI path.

### Root `App.js` and root `DashboardComponents.js`

Purpose: Older standalone React interface outside `frontend/`.

Inputs/outputs: Calls `http://localhost:8000` endpoints and displays NLICE tracker, urgency badge, RAG panel, and summary modal.

Interactions:

- Not the active Create React App entry point; active entry point is `frontend/src/App.js`.

### Test Files

Purpose: Lightweight direct tests/smoke scripts for agents and flow.

Examples:

- `test_voice.py`: calls `transcribe_audio("Recording.m4a")`.
- `test_chat_flow.py`: exercises chat controller flow.
- `test_*_agent.py`: direct agent smoke tests.
- `frontend/src/App.test.js`: default CRA test still expects "learn react", which does not match current app.

## 4. LangGraph Workflow

### State

`ClinicalState` tracks:

- messages
- demographics: `age_gender`
- complaint/duration/medications
- `nlice_data` and `nlice`
- urgency and urgency score
- step/case type
- vision output
- question lists and current question index
- patient answers and associated symptoms
- red flag screening flag
- allergies and past history
- clinical context, summary, normalized summary, recommendations
- validation warnings
- turn count
- conversation completion
- concept memory
- uncertainty count

### Nodes

`extract_info_node`

- Reads latest human message.
- Updates associated symptoms.
- Updates red-flag screening and concept memory.
- Infers target field from latest assistant question.
- Normalizes terse replies such as `8`, `no`, `morning`.
- Extracts NLICE using rules for intensity, location, fever, nature, medications, systemic terms, chronology, and excitation.
- Uses Gemini fallback extraction only when three or more fields remain missing and no contextual normalization happened.
- Validates clinical state.

`question_node`

- Sets max questions to `8` when priority follow-ups exist, otherwise `5`.
- Computes missing NLICE fields.
- Selects focus with `_select_question_focus()`.
- Prioritizes deterministic high-risk follow-up questions for high fever, chest pain, headache, and abdominal pain.
- Otherwise calls `clinical_exploration_agent()` for exploration or `followup_question_agent()` for NLICE.
- Checks semantic redundancy with previous questions and concept memory.
- Falls back to uncertainty-specific or static questions.

`summary_node`

- Applies emergency term override for chest pain, shortness of breath, difficulty breathing, stroke, severe bleeding.
- Otherwise calls `urgency_classifier_agent()`.
- Calls `clinical_context_agent()`.
- Calls `summary_agent()`, then normalizes the summary.
- Generates recommendations and validation warnings.

### Edges and Routing

```text
set_entry_point("extract_info_node")

extract_info_node
  -> should_continue()
       if conversation_complete:
          summary_node
       elif missing NLICE fields OR exploration incomplete:
          question_node
       else:
          summary_node

question_node -> END
summary_node  -> END
```

### Flow Diagram

```text
┌─────────────┐
│ Human turn  │
└──────┬──────┘
       ▼
┌───────────────────┐
│ extract_info_node  │
│ - NLICE update     │
│ - symptoms         │
│ - concept memory   │
└────────┬──────────┘
         ▼
┌───────────────────┐
│ should_continue    │
└──────┬───────┬────┘
       │       │
       │       ▼
       │  ┌──────────────┐
       │  │ summary_node │
       │  └──────┬───────┘
       │         ▼
       │        END
       ▼
┌───────────────────┐
│ question_node      │
│ - priority rules   │
│ - exploration RAG  │
│ - NLICE RAG        │
│ - fallback         │
└────────┬──────────┘
         ▼
        END
```

## 5. RAG Pipeline

### Follow-Up RAG Pipeline

Dataset source:

- `data/followup_q/train-00000-of-00001.parquet`
- Converted into `data/followupq.csv` by `data.py`.
- Indexed by `build_followup_index.py`.

Embedding model:

- `all-MiniLM-L6-v2` from `sentence-transformers`.

Vector store:

- FAISS `IndexFlatL2`.

Stored assets:

- `data/followup_q/followup_index.faiss`
- `data/followup_q/followup_records.pkl`

Retrieval flow:

```text
question_node
  -> mode exploration:
       clinical_exploration_agent()
  -> mode nlice:
       followup_question_agent()
  -> retrieve_followup_examples()
       -> lazy load SentenceTransformer
       -> lazy load FAISS index
       -> lazy load pickled records
       -> embed query
       -> index.search(top_k)
       -> return message/questions/ehr/distance examples
  -> prompt construction with examples + state + prior questions
  -> Gemini 2.5 Flash
  -> clean one question
  -> redundancy filter
  -> return to frontend
```

### Prompt Construction

`followup_question_agent.py` binds Gemini to:

- one target NLICE field;
- current NLICE state;
- associated symptoms;
- retrieved clinician examples;
- previous questions;
- recent conversation context;
- strict no diagnosis/no treatment/no tests rules.

`clinical_exploration_agent.py` binds Gemini to:

- an exploration focus such as `associated_symptoms`, `red_flags`, `contextual_followup`, or `nlice_blend`;
- retrieved examples;
- current NLICE and missing fields;
- strict single-question output.

### SymCAT RAG Pipeline

Dataset source:

- `data/symcat-801-diseases.csv`
- `data/symcat-474-symptoms.csv` is present, but the processing script uses the diseases CSV.

Embedding model:

- `all-MiniLM-L6-v2`.

Vector store:

- FAISS `IndexFlatL2`.

Runtime:

- `rag/retrieve_context.py` returns document strings to `agents/question_agent.py`.

Current status:

- Implemented and index assets exist.
- Not wired into the active LangGraph `question_node`.

## 6. Voice Pipeline

### Browser Microphone

`frontend/src/App.js` uses:

- `navigator.mediaDevices.getUserMedia()`
- `MediaRecorder`
- MIME preference: `audio/webm;codecs=opus`, fallback `audio/webm`
- one-second chunk interval
- echo cancellation, noise suppression, auto gain control, mono audio

### Upload Flow

```text
toggleRecording()
  -> startRecording()
  -> MediaRecorder collects chunks
  -> stopRecording()
  -> Blob(audio/webm)
  -> sendAudioToBackend()
  -> POST http://127.0.0.1:8000/voice
```

The frontend appends `language` when it can map the selected patient language to a code.

### FastAPI Endpoint

`main.py` `/voice`:

- reads uploaded audio bytes;
- determines suffix from MIME type/filename;
- saves a temporary audio file;
- calls `transcribe_audio(temp_path, language)`;
- returns transcript JSON;
- deletes temp file.

### Faster Whisper

`voice_service.py`:

- loads `WhisperModel("small", device="cpu", compute_type="int8")` at import time;
- decodes audio to 16 kHz;
- rejects audio shorter than 0.75 seconds;
- uses `beam_size=5`, `best_of=5`, `temperature=0`, `vad_filter=True`;
- logs average log probability, no-speech probability, compression ratio;
- discards suspicious transcripts like `...`.

### Clinical Workflow Integration

Voice currently stops at transcription. The frontend fills the text input with the transcript, and the patient/user must send it through the normal `/chat` flow. This is a deliberate integration boundary in the current code.

## 7. Clinical State Model

### Backend State Fields

`ClinicalState` tracks:

- `messages`
- `age_gender`
- `complaint`
- `duration`
- `medications`
- `nlice_data`
- `nlice`
- `urgency`
- `urgency_score`
- `step`
- `case_type`
- `vision_output`
- `questions`
- `exploration_questions`
- `current_question_index`
- `patient_answers`
- `associated_symptoms`
- `red_flags_screened`
- `allergies`
- `past_history`
- `clinical_context`
- `summary`
- `normalized_summary`
- `recommendations`
- `validation_warnings`
- `turn_count`
- `conversation_complete`
- `concept_memory`
- `uncertainty_count`

### NLICE Fields

- Nature: symptom quality or core symptom.
- Location: anatomical/systemic location.
- Intensity: severity, usually 1-10.
- Chronology: onset/duration/timing.
- Excitation: triggers, relievers, worsening factors, medication response.

### State Updates

Backend state updates occur in `extract_info_node()` through:

- regex/rule extraction;
- contextual answer normalization;
- associated symptom detection;
- red flag screening detection;
- concept memory updates;
- Gemini fallback extraction for sparse inputs;
- clinical state validation.

Frontend state updates occur in `syncClinicalState()` through:

- merging backend payload into previous dashboard state;
- parsing latest text for temperature, severity, duration;
- detecting symptoms and negative findings;
- scoring urgency;
- choosing modules;
- deriving timeline and summary.

### Summary Generation

Backend:

- `summary_node()` calls `summary_agent()` for a SOAP-style report.
- `_normalize_clinical_summary()` creates a concise normalized summary for dashboard use.

Frontend:

- `generateClinicalSummary()` creates a patient-demographic-aware summary from dashboard state.

### Triage Calculation

Backend:

- `summary_node()` has emergency term override.
- `urgency_classifier_agent()` predicts from synthetic RandomForest artifacts.
- `main._normalize_analysis()` applies additional rule-based score correction.

Frontend:

- `scoreClinicalUrgency()` calculates score and red flags from temperature, symptoms, breathing difficulty, severity, and symptom count.

## 8. Feature Inventory

| Feature | Purpose | File Location | Status |
|---|---|---|---|
| Text clinical intake | Guided symptom conversation | `frontend/src/App.js`, `main.py`, `chat_controller.py` | Implemented |
| LangGraph orchestration | Deterministic workflow control | `chat_controller.py` | Implemented |
| NLICE extraction | Structured symptom model | `chat_controller.py`, `clinicalState.js` | Implemented |
| Contextual follow-up generation | Clinician-style questions | `agents/followup_question_agent.py`, `agents/clinical_exploration_agent.py` | Implemented |
| Followup-Q RAG | Retrieve clinician examples | `followup_retriever.py`, `build_followup_index.py` | Implemented |
| SymCAT RAG | Retrieve symptom/disease context | `rag/*`, `agents/question_agent.py` | Implemented but not active in current graph |
| Voice intake | Browser mic to transcript | `frontend/src/App.js`, `main.py`, `voice_service.py` | Implemented |
| Multilingual voice | Whisper language hints | `frontend/src/App.js`, `voice_service.py` | Partially implemented: backend supports en/hi/bn; UI lists more |
| OCR / prescription reading | Extract readable image text | `main.py`, `reader_agent.py`, `gemini_vision_service.py` | Implemented backend; active frontend voice UI does not expose upload in current `frontend/src/App.js` |
| Adaptive dashboard | Clinical cards based on category | `AdaptiveDashboard.js`, `dashboardConfig.js`, `DashboardComponents.js`, `ClinicalModules.js` | Implemented |
| Timeline | Show recent clinical events | `clinicalState.js`, `DashboardComponents.js` | Implemented |
| SOAP/clinical summary | Doctor handoff summary | `summary_agent.py`, `chat_controller.py`, frontend cards | Implemented |
| Triage scoring | Urgency level and score | `chat_controller.py`, `main.py`, `urgency_classifier_agent.py`, `clinicalState.js` | Implemented with duplicated logic |
| ML urgency classifier | RandomForest over NLICE | `ml/urgency_model.py`, `agents/urgency_classifier_agent.py` | Implemented, synthetic data |
| PDF export | Export dashboard/report | `frontend/src/App.js` | Implemented |
| Local history | Save completed sessions | `frontend/src/App.js`, browser localStorage | Implemented |
| Streamlit UI | Alternative app interface | `app_streamlit.py`, `updated_app_streamlit.py` | Legacy/alternative |
| Safety flag extraction | Medication/allergy/chronic flags | `agents/safety_agent.py` | Implemented but not active in graph |
| Clinical synthesis JSON agent | Gemini NLICE synthesis | `agents/clinical_synthesis_agent.py` | Implemented but not active in graph |

## 9. Current Limitations

- Single global backend `ChatController` means sessions are not isolated despite `session_id` existing in `ChatRequest`.
- Clinical logic is duplicated across `chat_controller.py`, `main.py`, and `frontend/src/clinicalState.js`; triage/category results can diverge.
- `requirements.txt` omits active dependencies: `faster-whisper`, `faiss`, `sentence-transformers`, `numpy`, `streamlit`, and PDF/UI dependencies used by legacy apps.
- `followup_retriever.py`, `build_followup_index.py`, and `data.py` use hardcoded absolute Windows paths.
- `voice_service.py` loads Whisper at module import, which increases backend startup time and memory use.
- Voice language support mismatch: UI lists Tamil and Telugu, backend only explicitly accepts English, Hindi, Bengali.
- `/voice` returns transcript only; it does not automatically submit to `/chat`.
- `/upload` saves a temp file but passes only bytes to controller; temp path is unused.
- `handle_file()` is referenced by `main.py`; image upload is exposed in root legacy `App.js`, not in active `frontend/src/App.js`.
- Gemini clients are created at import time in several modules; missing `GEMINI_API_KEY` can fail imports for some agents.
- `services/gemini_vision_service.py` always sends uploaded images as `image/jpeg`.
- The ML urgency model is trained on synthetic data and limited NLICE features, so it is a prototype rather than clinically validated triage.
- `agents/clinical_synthesis_agent.py`, `safety_agent.py`, `complaint_agent.py`, and `question_agent.py` are implemented but not wired into the active graph.
- `frontend/src/App.test.js` is still the default Create React App test and does not match the current UI.
- Some existing docs mention old performance numbers and complete states that are not enforced by automated tests.
- No authentication, persistence database, audit log, PHI security model, or production deployment configuration exists.

## 10. Future Roadmap

### Short Term

- Replace hardcoded paths with `Path(__file__).resolve()` relative paths in follow-up RAG scripts.
- Update `requirements.txt` to match active imports.
- Fix the frontend test or remove the default CRA assertion.
- Add per-session controller storage keyed by `session_id`.
- Align voice language UI with backend support or add explicit Tamil/Telugu handling.
- Expose image upload in the active `frontend/src/App.js` if OCR is part of the demo path.
- Add smoke tests for `/chat`, `/voice`, retriever loading, and summary generation.

### Medium Term

- Consolidate triage/category logic into one backend service and make the frontend display rather than re-score.
- Add a structured API contract for clinical state instead of loosely merged dictionaries.
- Add RAG evaluation fixtures for question quality, repetition avoidance, and retrieval relevance.
- Improve urgency classifier training data or replace it with transparent rule-based triage plus model explanation.
- Add session persistence, audit events, and doctor handoff report storage.
- Add better error surfaces for missing Gemini key, missing FAISS assets, and missing Whisper dependencies.

### Long Term

- Build a clinician-reviewed triage reasoning module with explicit red-flag protocols.
- Add multilingual end-to-end intake, not just transcription.
- Add secure authentication, encrypted storage, consent, PHI handling, and audit trails.
- Add EHR/FHIR-compatible export.
- Add model monitoring and regression evaluation for clinical summaries and follow-up questions.
- Move toward clinically validated datasets and review workflows before any real-world medical use.

## Where SevaCare AI Currently Stands

Completed:

- Active React + FastAPI app path.
- LangGraph conversation controller.
- NLICE extraction and state tracking.
- Retrieval-augmented follow-up questions using Followup-Q FAISS examples.
- Faster Whisper voice transcription endpoint and browser recording.
- Adaptive dashboard with triage, summary, timeline, and PDF export.
- Gemini-based clinical context and image reading support.

Partially completed:

- Multilingual support is present for voice transcription hints but not complete across UI/backend.
- OCR exists in backend/legacy UI but is not surfaced in active frontend.
- SymCAT RAG exists but is not part of the active LangGraph flow.
- ML urgency exists but is synthetic and supplemented by rule-based scoring.
- Clinical state exists in both backend and frontend with overlapping derivation.

Should be built next:

- Per-session backend state.
- Dependency and path cleanup.
- Unified clinical state/triage service.
- Active UI upload path for prescription OCR.
- Automated tests around the graph, RAG fallback, voice endpoint, and dashboard state sync.
