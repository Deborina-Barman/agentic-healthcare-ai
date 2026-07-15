# Migration Plan

## Objective

Move SevaCare from concept/RAG-centered question selection to workflow-driven question selection without breaking existing LangGraph flow, summary generation, dashboard response shape, or NLICE support.

No new agents, no extra RAG, and no fine-tuning are required.

## Current Code Locations

Primary files:

- `chat_controller.py`
- `clinical_workflows.py`
- `agents/clinical_exploration_agent.py`
- `agents/followup_question_agent.py`
- `main.py`
- `frontend/src/clinicalState.js`

Primary functions in `chat_controller.py`:

- `ClinicalState`
- `_empty_nlice()`
- `_missing_nlice_fields()`
- `_extract_associated_symptoms()`
- `_update_concept_memory()`
- `_priority_followup_questions()`
- `_priority_followup_question()`
- `_priority_followups_complete()`
- `_conversation_target_field()`
- `_normalize_contextual_reply()`
- `extract_info_node()`
- `_exploration_is_complete()`
- `_select_question_focus()`
- `question_node()`
- `should_continue()`
- `summary_node()`

## Phase 1: Add Structured State Without Changing Behavior

Location:

- `ClinicalState` in `chat_controller.py`
- `ChatController.__init__()`

Add optional fields:

- `workflow_key`
- `clinical_fields`
- `workflow_progress`
- `safety`

Keep existing fields:

- `nlice_data`
- `nlice`
- `associated_symptoms`
- `red_flags_screened`
- `concept_memory`
- `questions`
- `exploration_questions`
- `medications`
- `urgency`
- `summary`

Reason:

The first migration step should be additive. Existing UI and summary paths continue reading current fields while V2 state begins accumulating structured evidence.

## Phase 2: Expand Extraction Into Structured Fields

Location:

- `extract_info_node()`
- `_normalize_contextual_reply()`
- helper extraction functions near current NLICE helpers.

Change:

- Continue updating `nlice_data`.
- Also update `clinical_fields`.
- Store field evidence with source turn and text.

Examples:

- `105` after a temperature question becomes `clinical_fields.temperature_max = 105`.
- `paracetamol` after a medication question becomes:
  - `medication_taken = true`
  - `medication_name = "paracetamol"`
  - `medication_response` remains missing.
- `yes` after hydration question becomes:
  - `hydration_status = "ok"`
  - `urination_normal = true`

What remains unchanged:

- existing NLICE rule extraction;
- associated symptom extraction;
- current message append/invoke flow.

## Phase 3: Identify Workflow Key

Location:

- end of `extract_info_node()`
- or a small helper called from it.

Use:

- `clinical_workflows.workflow_key_for_complaint()`
- complaint text;
- `nlice_data.nature`;
- associated symptoms if primary complaint is vague.

Store:

- `state["workflow_key"]`

Fallback:

- if no workflow matches, keep current NLICE-driven selection.

## Phase 4: Replace Priority Followups With Workflow Missing Fields

Location:

- `_priority_followup_questions()`
- `_priority_followup_question()`
- `_priority_followups_complete()`

Change:

- De-emphasize hardcoded priority tuples.
- Use `CLINICAL_WORKFLOWS[workflow_key]["priority_order"]`.
- Use structured field completion rather than concept memory.

Preserve:

- existing hardcoded priority questions as fallback templates where they match workflow fields.
- current high-fever questions, but assign them to fields:
  - medication question -> `medication_taken` and `medication_response`
  - hydration question -> `hydration_status`
  - vomiting question -> `vomiting_diarrhea`
  - travel question -> `exposure_infection`

## Phase 5: Rewrite Selection Logic Around Workflow Target

Location:

- `_select_question_focus()`
- `question_node()`

New target selection:

```text
workflow exists
-> get missing workflow fields
-> apply risk overrides
-> select highest-priority missing field
-> ask field question
```

Fallback order:

1. workflow field question;
2. existing phrasing agent using target field as context;
3. safe static workflow question;
4. generic NLICE fallback only outside configured workflows.

Important:

`EXPLORATION_FALLBACK_MAP["priority_followup"]` should be removed or replaced with a concrete safety question. No high-risk branch should have an abstract fallback.

## Phase 6: Reposition Concept Memory

Location:

- `_update_concept_memory()`
- `_is_semantically_redundant_question()`
- `question_node()`

Change:

- Keep concept memory for repetition control.
- Stop using concept memory as proof that a clinical field is complete.
- Add `asked_fields` and `completed_fields` to `workflow_progress`.

Preserve:

- uncertainty handling;
- semantic duplicate checks;
- explored concept logs for debugging.

## Phase 7: Completion Logic

Location:

- `_exploration_is_complete()`
- `should_continue()`

Change completion from:

```text
NLICE missing OR exploration incomplete
```

to:

```text
workflow required fields missing
OR risk-promoted fields missing
OR red flags not screened when required
OR minimum NLICE summary fields missing
```

Preserve:

- max-question loop protection.

Improve:

- if max question count is reached in a high-risk incomplete workflow, produce a concrete safety handoff summary rather than another weak question.

## Phase 8: Keep Existing Agents As Phrasing Layers

Locations:

- `clinical_exploration_agent()`
- `followup_question_agent()`

No new agents.

No more RAG.

Future use:

- pass selected workflow field as target;
- pass field question as a grounding template;
- reject outputs that do not ask about the selected field.

Fallback:

- the workflow field question should always be acceptable.

## Phase 9: Preserve Frontend And API Compatibility

Location:

- `ChatController.handle_text()`
- `main.py::_unified_response()`
- `frontend/src/clinicalState.js`

Preserve existing response fields:

- `message`
- `nlice_data`
- `associated_symptoms`
- `summary`
- `recommendations`
- `validation_warnings`
- `concept_memory`
- `clinical_analysis`
- `is_complete`

Add optional fields:

- `workflow_key`
- `clinical_fields`
- `workflow_progress`
- `safety`

Frontend can adopt them gradually.

## Phase 10: Test Migration

Add tests for:

- fever with 105 F does not ask generic priority fallback;
- paracetamol alone leaves `medication_response` missing;
- hydration yes fills hydration fields;
- cough workflow asks shortness of breath/wheezing before generic follow-up;
- chest pain workflow prioritizes shortness of breath, radiation, dizziness, palpitations;
- abdominal pain workflow prioritizes GI/blood/hydration fields;
- concept memory cannot mark a workflow field complete without evidence.

## What Changes

- Question selection becomes workflow-field-driven.
- Temperature, medication response, hydration, and red flags become structured state.
- High-risk workflows use concrete safety fallbacks.
- Completion becomes answer-aware.

## What Remains Unchanged

- LangGraph node structure can remain.
- NLICE extraction remains.
- Summary generation remains.
- Existing agents remain available for phrasing.
- Existing RAG index remains available but is not expanded.
- Concept memory remains, but with narrower responsibility.

## Safe Implementation Order

1. Add structured state fields.
2. Add extraction into structured fields.
3. Add workflow-key detection.
4. Add missing-field computation.
5. Switch `question_node()` to use workflow target first.
6. Keep NLICE fallback for unknown workflows.
7. Add tests for the debug fever conversation.
8. Consolidate triage only after question selection is stable.

## Success Criteria

For the debug conversation, V2 should produce:

```text
With this fever, are you having trouble breathing, confusion, stiff neck, severe weakness, persistent vomiting, chest pain, fainting, rash, or signs of dehydration?
```

or:

```text
After taking paracetamol, did the fever come down, and what is your temperature now?
```

It should never produce:

```text
Can you share one more detail about the higher-risk symptom pattern?
```
