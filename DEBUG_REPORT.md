# SevaCare Question Selection Debug Report

## Scope

This report traces the current question-selection behavior for this exact conversation:

```text
Patient: I have fever for 3 days
Assistant: What other symptoms have you been experiencing along with the fever?
Patient: cough
Assistant: What has been the highest temperature you've measured?
Patient: 105
Assistant: Have you taken any fever medicine such as paracetamol or ibuprofen, and did the temperature come down?
Patient: paracetamol
Assistant: Are you able to drink fluids and urinate normally?
Patient: yes
Assistant: Can you share one more detail about the higher-risk symptom pattern?
```

No code changes were made. This is an explanation of the current behavior.

## Key Code Locations

- `chat_controller.py:149-193` checks missing NLICE fields.
- `chat_controller.py:549-590` updates concept memory.
- `chat_controller.py:774-844` defines and selects priority follow-up questions.
- `chat_controller.py:939-975` detects high fever from conversation text.
- `chat_controller.py:1231-1257` decides whether exploration is complete.
- `chat_controller.py:1260-1301` selects the next question mode and target.
- `chat_controller.py:1304-1508` infers which NLICE slot a short answer probably answered.
- `chat_controller.py:1556-1996` extracts symptoms, NLICE, medications, red-flag screening state, and concept memory.
- `chat_controller.py:2004-2273` generates or falls back to the next assistant question.
- `agents/clinical_exploration_agent.py` generates exploration questions using retrieval plus Gemini, with deterministic fallback.
- `agents/followup_question_agent.py` generates NLICE-targeted questions using retrieval plus Gemini, with deterministic fallback.
- `followup_retriever.py` retrieves clinician example questions from FAISS.
- `main.py:84-145` normalizes dashboard urgency score from backend state.
- `frontend/src/clinicalState.js:211-278` independently scores frontend triage.

## Current Pipeline Summary

Each user turn goes through:

1. `ChatController.handle_text()` appends the patient message and invokes the graph.
2. `extract_info_node()` updates:
   - `nlice_data`
   - `associated_symptoms`
   - `red_flags_screened`
   - `concept_memory`
   - `medications`
3. `should_continue()` sends the graph to `question_node()` if NLICE is missing or exploration is incomplete.
4. `question_node()` chooses:
   - priority high-risk follow-up, if `_priority_followup_question(state)` returns one;
   - associated symptom exploration;
   - NLICE blend exploration;
   - red-flag exploration;
   - a strict NLICE field question;
   - summary, if complete.
5. The selected question can come from:
   - `_priority_followup_question()` directly;
   - `clinical_exploration_agent()`;
   - `followup_question_agent()`;
   - static fallback maps in `question_node()`.

## Execution Trace

### Turn 1: Patient says "I have fever for 3 days"

Current clinical state:

- Complaint becomes `"I have fever for 3 days"`.
- Cleaned clinical complaint is effectively fever.
- Associated symptoms are empty.
- No temperature value is known yet.

Current NLICE state:

```json
{
  "nature": "fever",
  "location": "Systemic/General",
  "intensity": "",
  "chronology": "3 days",
  "excitation": ""
}
```

Symptoms detected:

- Fever as primary nature.
- No associated symptom from `ASSOCIATED_SYMPTOM_TERMS`.

Red flags detected:

- None.
- `red_flags_screened = false`.

Triage score:

- `chat_controller` still exposes `urgency_score` as `0` during intake.
- Dashboard scoring would remain low/moderate until a temperature is known.

Missing fields:

- `intensity`
- `excitation`

Concept memory state:

```json
{
  "explored": [],
  "uncertain": []
}
```

Candidate questions considered:

- `_priority_followup_question()` returns none because `_has_high_fever(state)` is false without a measured temperature.
- `_select_question_focus()` sees no exploration questions and chooses `("exploration", "associated_symptoms")`.
- `clinical_exploration_agent()` is called for associated symptoms.
- Static fallback, if needed: "I'm sorry you're not feeling well. Have you noticed chills, cough, body aches, vomiting, breathing trouble, or headache along with it?"

Why the chosen question won:

- Associated symptom exploration is the first deterministic exploration step.
- The generated question asks about symptoms along with fever.

Function generated it:

- `question_node()` selected focus.
- `clinical_exploration_agent()` likely generated the exact wording.

### Turn 2: Patient says "cough"

Current clinical state:

- Complaint remains fever for 3 days.
- Associated symptoms now include cough.
- No measured temperature is stored in NLICE yet.

Current NLICE state:

```json
{
  "nature": "fever",
  "location": "Systemic/General",
  "intensity": "",
  "chronology": "3 days",
  "excitation": ""
}
```

Symptoms detected:

- `cough` via `_extract_associated_symptoms()`.

Red flags detected:

- None.
- `red_flags_screened = false`.

Triage score:

- `chat_controller` still reports score `0`.
- `main.py`/frontend dashboard logic may add a respiratory symptom point if cough is in the unified state, but without temperature this is still low.

Missing fields:

- `intensity`
- `excitation`

Concept memory state:

Expected:

```json
{
  "explored": ["associated_symptoms"],
  "uncertain": []
}
```

Reason:

- The previous assistant question contains "other symptoms" and "along with", which map to `associated_symptoms`.
- The patient answer contains `cough`, also mapped under associated symptoms.

Candidate questions considered:

- High-fever priority is still unavailable because no temperature has been detected.
- `_select_question_focus()` sees:
  - at least one exploration question,
  - associated symptoms present,
  - missing NLICE fields,
  - fewer than two exploration questions.
- It chooses `("exploration", "nlice_blend")`.
- `clinical_exploration_agent()` is called with focus `nlice_blend`.
- Static fallback, if needed: "Have you checked the temperature, and does it improve after medication or worsen at certain times?"

Why the chosen question won:

- The system tries to blend clinical exploration with missing NLICE completion.
- The chosen question asks for measured temperature, which is clinically useful but does not map cleanly into the NLICE schema.

Function generated it:

- `question_node()` selected `nlice_blend`.
- `clinical_exploration_agent()` likely generated "What has been the highest temperature you've measured?"

### Turn 3: Patient says "105"

Current clinical state:

- Fever with cough.
- Measured temperature is discoverable from messages by `_state_temperature()`.
- Temperature is not stored as a first-class clinical field in `chat_controller`.
- The value `105` is not accepted as NLICE intensity because the intensity parser only accepts `1` through `10`.

Current NLICE state:

```json
{
  "nature": "fever",
  "location": "Systemic/General",
  "intensity": "",
  "chronology": "3 days",
  "excitation": ""
}
```

Symptoms detected:

- Existing: cough.
- No new associated symptom.

Red flags detected:

- Very high fever is recognized indirectly by `_has_high_fever()`.
- It is not stored in `red_flags_screened`.

Triage score:

- `chat_controller` still reports score `0` during intake.
- `main.py` dashboard normalization would score approximately `7`:
  - `+6` for temperature `>= 105 F`
  - `+1` for respiratory symptom/cough
  - level: `High`
- Frontend `scoreClinicalUrgency()` similarly scores approximately `7`:
  - `+6` very high fever
  - `+1` respiratory symptom
  - level: `High`

Missing fields:

- `intensity`
- `excitation`

Concept memory state:

Expected:

```json
{
  "explored": ["associated_symptoms"],
  "uncertain": []
}
```

The temperature question does not map to a durable concept such as `temperature`; no such concept exists.

Candidate questions considered:

Because `_has_high_fever(state)` is now true, `_priority_followup_questions()` returns:

1. Medication: "Have you taken any fever medicine such as paracetamol or ibuprofen, and did the temperature come down?"
2. Hydration: "Are you able to drink fluids and urinate normally?"
3. Associated/systemic symptoms: "Are you having chills, body aches, sweating, or severe weakness with the fever?"
4. Vomiting/diarrhea: "Any vomiting or diarrhea since the fever started?"
5. Travel/mosquito exposure: "Any recent travel, mosquito exposure, or time spent in an area with dengue or malaria risk?"
6. Infectious exposure: "Has anyone around you had a recent fever, cough, flu, COVID, or other infection?"

Why the chosen question won:

- Medication is the first high-fever priority follow-up.
- It was not yet explored and was not semantically redundant with previous questions.

Function generated it:

- `_priority_followup_question()` generated the selected question directly.
- `question_node()` accepted it before calling retrieval/Gemini.

### Turn 4: Patient says "paracetamol"

Current clinical state:

- Fever for 3 days.
- Cough.
- Highest measured temperature: 105 F, discoverable from messages.
- Medication taken: paracetamol.
- Medication response is still unknown because the patient did not answer whether the temperature came down.

Current NLICE state:

```json
{
  "nature": "fever",
  "location": "Systemic/General",
  "intensity": "",
  "chronology": "3 days",
  "excitation": ""
}
```

Important extraction issue:

- `_conversation_target_field()` still returns `intensity` because the medication question does not match its excitation hints well enough.
- `_normalize_contextual_reply()` only turns `paracetamol` into excitation if `target_field == "excitation"`.
- Therefore `paracetamol` updates top-level `medications`, but not `nlice_data.excitation`.

Symptoms detected:

- Existing: cough.
- No new associated symptom.

Red flags detected:

- Very high fever remains present by message scan.
- No explicit red-flag symptom reported.
- `red_flags_screened` remains false.

Triage score:

- `chat_controller`: still `0` during intake.
- `main.py`/frontend: approximately `7`, High, because `105 F` plus cough are in the text/state.

Missing fields:

- `intensity`
- `excitation`

Concept memory state:

Expected:

```json
{
  "explored": ["associated_symptoms", "medication", "severity"],
  "uncertain": []
}
```

Why `severity` can appear:

- `_conversation_target_field()` defaults to the first missing field, `intensity`.
- `_update_concept_memory()` can add `CONCEPT_FOR_TARGET["intensity"] == "severity"` when the previous assistant message has recognized concepts.
- This is a concept-memory false positive: a medication answer may mark severity as explored.

Candidate questions considered:

High-fever priorities are still active:

1. Medication: skipped because medication is now explored.
2. Hydration: available.
3. Associated/systemic symptoms.
4. Vomiting/diarrhea.
5. Travel/mosquito exposure.
6. Infectious exposure.

Why the chosen question won:

- Hydration is the next non-explored high-fever priority concept.

Function generated it:

- `_priority_followup_question()` generated the selected question directly.
- `question_node()` accepted it before calling retrieval/Gemini.

### Turn 5: Patient says "yes"

Current clinical state:

- Fever for 3 days.
- Cough.
- Highest measured temperature: 105 F.
- Paracetamol taken.
- Hydration/urination question answered yes.
- Medication response remains unknown.
- Red-flag screen remains incomplete.

Current NLICE state:

```json
{
  "nature": "fever",
  "location": "Systemic/General",
  "intensity": "",
  "chronology": "3 days",
  "excitation": ""
}
```

Symptoms detected:

- Existing: cough.
- No new associated symptom from "yes".

Red flags detected:

- Very high fever remains present.
- No explicit dangerous symptom has been confirmed or denied.
- `red_flags_screened = false`.

Triage score:

- `chat_controller`: still reports score `0` until summary/normalization.
- `main.py`: approximately `7`, High.
- Frontend: approximately `7`, High.

Missing fields:

- `intensity`
- `excitation`

Concept memory state:

Expected:

```json
{
  "explored": ["associated_symptoms", "hydration", "medication", "severity"],
  "uncertain": []
}
```

Candidate questions considered:

High-fever priorities should still include:

1. Associated/systemic symptoms: may be skipped if associated symptoms were already explored.
2. Vomiting/diarrhea: should generally still be available.
3. Travel/mosquito exposure: should generally still be available.
4. Infectious exposure: should generally still be available.

The exact weak final question:

```text
Can you share one more detail about the higher-risk symptom pattern?
```

is not produced by the retrieval agents. It is the static fallback for `priority_followup` in `question_node()`:

```python
EXPLORATION_FALLBACK_MAP = {
    ...
    "priority_followup":
        "Can you share one more detail about the higher-risk symptom pattern?",
}
```

Why the chosen question won:

- `_select_question_focus()` entered priority exploration because `_priority_followup_question(state)` was still non-null.
- The direct concrete priority candidate was not accepted into `question`.
- `clinical_exploration_agent()` was then called with focus `"priority_followup"`, a focus not defined in `FOCUS_GUIDANCE`.
- The returned/generated candidate was either unavailable, failed, or rejected as semantically redundant.
- `question_node()` fell through to the static exploration fallback for `"priority_followup"`.

Function generated it:

- `question_node()` generated it from `EXPLORATION_FALLBACK_MAP`.
- It was not generated by `_priority_followup_questions()`, `clinical_exploration_agent()`, or `followup_question_agent()`.

## Direct Answers

### A. Why was "Can you share one more detail about the higher-risk symptom pattern?" selected?

It was selected because `question_node()` was in `("exploration", "priority_followup")` mode and failed to produce an acceptable concrete priority question. When no question is set, `question_node()` uses `EXPLORATION_FALLBACK_MAP["priority_followup"]`, which is exactly:

```text
Can you share one more detail about the higher-risk symptom pattern?
```

The clinical weakness is caused by a generic static fallback for a high-risk branch.

### B. Was there a better question available?

Yes.

From `_priority_followup_questions()` for high fever, better available questions include:

- "Any vomiting or diarrhea since the fever started?"
- "Any recent travel, mosquito exposure, or time spent in an area with dengue or malaria risk?"
- "Has anyone around you had a recent fever, cough, flu, COVID, or other infection?"

Also, because `red_flags_screened` is still false, a better safety question would be:

```text
With a temperature of 105 F, are you having trouble breathing, confusion, stiff neck, severe weakness, persistent vomiting, chest pain, fainting, or signs of dehydration?
```

### C. Should intake have ended at that point?

No.

Intake should not have ended because:

- Temperature 105 F is high risk.
- `red_flags_screened` is still false.
- Priority high-fever follow-ups are not complete.
- NLICE fields `intensity` and `excitation` are still missing.
- The medication response was not captured; "paracetamol" answers what was taken, not whether it worked.

Clinically, the system should probably escalate/advise urgent assessment while asking a concise red-flag screen.

### D. Which fields were still missing?

Backend NLICE fields still missing:

- `intensity`
- `excitation`

Clinically important missing details:

- Did paracetamol reduce the temperature?
- Current temperature after medication.
- Dose/timing of paracetamol.
- Breathing difficulty.
- Confusion/altered mental status.
- Stiff neck.
- Severe weakness.
- Persistent vomiting.
- Rash.
- Dehydration signs beyond basic fluid/urine yes/no.
- Exposure/travel/mosquito risk.
- Age and comorbidity risk, if relevant to intake scope.

### E. What would an ideal clinician ask next?

Best next question:

```text
Since 105 F is a very high fever, are you having any trouble breathing, confusion, stiff neck, severe weakness, persistent vomiting, chest pain, fainting, rash, or worsening dehydration?
```

If asking only about the medication gap:

```text
After taking paracetamol, did the fever come down, and what is your temperature now?
```

### F. Which code location is responsible for this behavior?

Primary responsibility:

- `chat_controller.py:2079-2095`: static `EXPLORATION_FALLBACK_MAP`, especially `"priority_followup"`.
- `chat_controller.py:2100-2112`: direct priority candidate acceptance/rejection.
- `chat_controller.py:2118-2158`: fallback to `clinical_exploration_agent()` when the direct priority question is not accepted.
- `chat_controller.py:2231-2253`: final static fallback when no agent/direct question survives.

Contributing responsibility:

- `chat_controller.py:1279-1280`: priority mode takes over whenever `_priority_followup_question(state)` is non-null.
- `chat_controller.py:823-835`: concrete priority question selection can skip candidates due explored concepts or asked-text checks.
- `chat_controller.py:671-692`: semantic redundancy can reject a clinically useful candidate based on concept memory or lexical overlap.
- `chat_controller.py:1304-1383`: target-field inference defaults terse replies to the first missing NLICE field.
- `chat_controller.py:1419-1466`: medication answers only fill excitation when the inferred target is `excitation`.
- `chat_controller.py:1582-1586`: concept memory is updated before current-turn extraction and can inherit wrong target assumptions.

## Root Cause Analysis

### Root Cause 1: Generic fallback for a high-risk branch

The exact weak question is hardcoded. It is a placeholder-style sentence used when priority follow-up selection fails.

For a safety-sensitive branch, the fallback should never be abstract. It should degrade to a concrete red-flag or high-fever question.

### Root Cause 2: No first-class temperature field

The measured `105` is detected only by scanning messages in `_state_temperature()`. It is not stored as a structured field like `temperature_max`.

This causes downstream problems:

- NLICE remains incomplete.
- Question generation cannot reliably use temperature as structured context.
- Medication response is not tied to the fever measurement.
- Dashboard triage and backend intake logic derive risk separately.

### Root Cause 3: NLICE target inference misclassifies medication reply

After the medication question, the patient says "paracetamol".

The code should treat this as medication/excitation context. Instead:

- `_conversation_target_field()` sees missing `intensity` before `excitation`.
- The medication question does not match excitation hints strongly enough.
- `_normalize_contextual_reply()` does not fill `excitation`.
- `medications` is updated, but `nlice_data.excitation` remains blank.

### Root Cause 4: Concept memory can record false positives

Because target inference defaults to `intensity`, `_update_concept_memory()` can mark `severity` as explored during a medication exchange.

That can suppress later severity/intensity questions even though the patient never rated severity.

### Root Cause 5: Priority follow-up completion is concept-based, not answer-quality-based

Medication is considered explored if medication-related words appear. The system does not verify whether both parts of the medication question were answered:

- medicine taken?
- did fever come down?

The patient answered only the first part.

### Root Cause 6: `priority_followup` is not a real exploration focus

`clinical_exploration_agent.FOCUS_GUIDANCE` has:

- `associated_symptoms`
- `red_flags`
- `contextual_followup`
- `nlice_blend`

It does not define `priority_followup`. When `question_node()` calls the agent with focus `"priority_followup"`, the prompt falls back to contextual guidance. This weakens the agent branch and increases the chance of a rejected or generic candidate.

### Root Cause 7: Completion logic is not aligned with clinical risk

`_exploration_is_complete()` requires high-fever priority follow-ups to complete, but the fallback question can satisfy the loop count without actually collecting clinically useful information.

The system can therefore continue asking low-value questions instead of forcing a concrete red-flag screen or escalation.

## Recommended Fixes

Do not implement yet; these are design recommendations.

### Priority 1: Replace the `priority_followup` fallback

Replace:

```text
Can you share one more detail about the higher-risk symptom pattern?
```

with a concrete fever safety fallback:

```text
With a temperature this high, are you having trouble breathing, confusion, stiff neck, severe weakness, persistent vomiting, chest pain, fainting, rash, or signs of dehydration?
```

### Priority 2: Add structured temperature state

Add fields such as:

- `temperature_max`
- `temperature_current`
- `temperature_unit`
- `fever_reduced_after_medication`

Then use those fields in:

- priority follow-up selection
- completion logic
- summary
- dashboard triage

### Priority 3: Make high-fever priority questions answer-aware

Track priority items as structured checklist entries:

```json
{
  "medication_taken": true,
  "medication_response_known": false,
  "hydration_screened": true,
  "vomiting_diarrhea_screened": false,
  "danger_red_flags_screened": false,
  "exposure_screened": false
}
```

Do not treat a concept as complete just because a keyword was mentioned.

### Priority 4: Add excitation hints for medication-response questions

Include hints like:

- "medicine"
- "fever medicine"
- "paracetamol"
- "ibuprofen"
- "temperature come down"
- "did it come down"
- "after taking"

This would allow `_conversation_target_field()` to infer `excitation` for the paracetamol reply.

### Priority 5: Separate severity from temperature

Do not let a measured fever value like `105` compete with NLICE `intensity`.

For fever, `intensity` could be:

- patient-perceived severity, or
- omitted/deprioritized in favor of structured temperature.

But `105` should be treated as temperature, not ignored and not severity.

### Priority 6: Add a real `priority_followup` focus to `clinical_exploration_agent`

Add explicit guidance:

```text
Ask the highest-yield remaining concrete safety or fever-priority question. Do not ask abstract meta-questions.
```

### Priority 7: Consolidate triage scoring

Currently:

- `chat_controller` reports score `0` during intake.
- `main.py` computes a backend dashboard score.
- `frontend/src/clinicalState.js` computes another score.
- `summary_node()` uses ML urgency without returning a consistent numeric score.

This can make question selection, dashboard display, and final summary disagree.

Create one backend triage service and make the frontend display it.

## Priority-Ranked Improvements

1. Remove the generic high-risk fallback and replace it with concrete red-flag screening.
2. Store temperature as structured state immediately when detected.
3. Track high-fever priority checklist completion by answer quality, not concept keywords.
4. Fix medication-response extraction so `paracetamol` after a medication question updates medication state and asks whether fever came down.
5. Add a mandatory red-flag screen before any abstract contextual follow-up in high-fever cases.
6. Prevent concept memory from marking `severity` explored unless a severity/intensity answer was actually captured.
7. Add test coverage for the exact conversation in this report.
8. Add a trace/debug mode that logs selected mode, target, candidates, rejection reasons, and generator source per turn.
9. Consolidate backend/frontend triage scoring.
10. Review whether NLICE is the right schema for fever, since fever needs temperature, duration, antipyretic response, hydration, and red-flag protocol more than pain-style NLICE fields.

## Bottom Line

The final question is weak because the high-fever priority branch fell through to a generic static fallback. The code had enough clinical context to ask a better question. At that point, intake should not have ended, but it also should not have asked an abstract "higher-risk symptom pattern" question. It should have asked a concrete danger-symptom screen or clarified whether paracetamol reduced the 105 F fever.
