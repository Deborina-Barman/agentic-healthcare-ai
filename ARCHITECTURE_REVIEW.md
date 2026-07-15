# SevaCare V2 Architecture Review

## Current Architecture

SevaCare currently uses a LangGraph intake loop centered on `chat_controller.py`.

Current flow:

```text
Patient message
-> extract_info_node()
-> should_continue()
-> question_node() or summary_node()
-> assistant question or summary
```

`extract_info_node()` performs mixed state extraction:

- rule-based NLICE extraction;
- associated symptom extraction;
- medication keyword detection;
- red-flag screening state;
- concept memory updates;
- optional Gemini fallback extraction when many NLICE fields remain missing.

`question_node()` then decides what to ask next using:

- `_missing_nlice_fields()`;
- `_select_question_focus()`;
- `_priority_followup_question()`;
- `concept_memory`;
- semantic duplicate checks;
- `clinical_exploration_agent()`;
- `followup_question_agent()`;
- static fallback maps.

The current design is not purely RAG. It already has deterministic pieces, especially `_priority_followup_questions()` and high-fever handling. But those pieces are not organized as complaint-specific workflows. They sit beside NLICE and concept memory rather than owning the clinical sequence.

## Strengths

The current system has several useful foundations:

- LangGraph keeps extraction, question selection, and summary as distinct graph nodes.
- NLICE gives a consistent minimum structure for symptom history.
- Rule-based extraction captures common terse answers such as duration, simple severity, fever, body location, medication names, and associated symptoms.
- `concept_memory` reduces repeated questions.
- `_priority_followup_questions()` already recognizes that high fever, chest pain, headache, and abdominal pain need special questions.
- Retrieval and Gemini are constrained to question phrasing rather than freeform diagnosis.
- The frontend and backend already expose clinical state, summary, urgency, recommendations, and active dashboard modules.

## Weaknesses

### 1. No Structured Clinical State Model

The system stores some facts in NLICE, some in top-level fields, some in associated symptom strings, and some only in raw messages.

Example:

- Fever duration is stored in `nlice_data.chronology`.
- Fever nature is stored in `nlice_data.nature`.
- Cough is stored in `associated_symptoms`.
- Paracetamol is stored in `medications`.
- Temperature `105` is only discoverable by scanning the message history.
- Medication response is not stored at all.
- Hydration answer is not stored as a structured field.

Because fields are scattered, question selection cannot reliably ask "what is still missing clinically?"

### 2. NLICE Is Being Asked to Carry Too Much

NLICE works well for symptom characterization:

- nature
- location
- intensity
- chronology
- excitation

But fever workflows need additional structured facts:

- temperature max;
- current temperature;
- medication taken;
- medication response;
- hydration/urination;
- vomiting/diarrhea;
- respiratory symptoms;
- exposure;
- red flags.

Trying to force these into `intensity` or `excitation` causes weak routing. In the fever example, `105` is a temperature, not NLICE intensity. `paracetamol` is medication taken, not necessarily an excitation/relieving factor unless response is known.

### 3. Question Selection Is Concept-Driven Instead Of Field-Driven

`concept_memory` records broad concepts such as:

- medication
- hydration
- severity
- associated_symptoms

This helps prevent repetition, but it is not enough to determine completion.

Example:

The patient says `paracetamol`. Concept memory may mark medication as explored, but the system still does not know:

- dose;
- timing;
- whether the fever came down;
- current temperature.

Concept completion is not the same as clinical field completion.

### 4. Priority Questions Are Not Answer-Aware

`_priority_followup_questions()` returns question candidates, but completion is inferred indirectly from concepts and asked text.

This leads to false completion:

```text
Assistant: Have you taken fever medicine, and did the temperature come down?
Patient: paracetamol
```

The system marks medication explored, although only half the question was answered.

### 5. High-Risk Fallbacks Can Be Generic

The weak final question comes from `EXPLORATION_FALLBACK_MAP["priority_followup"]`:

```text
Can you share one more detail about the higher-risk symptom pattern?
```

This is a placeholder-style fallback in a safety-sensitive branch. If the system is in a high-risk workflow, the fallback should be concrete and clinically scoped.

### 6. `priority_followup` Is Not A Real Agent Focus

`clinical_exploration_agent.FOCUS_GUIDANCE` supports:

- `associated_symptoms`
- `red_flags`
- `contextual_followup`
- `nlice_blend`

It does not define `priority_followup`. When `question_node()` passes that focus, the prompt falls back to contextual guidance, which weakens the branch.

### 7. Triage Logic Is Split

Urgency/triage is computed in multiple places:

- `chat_controller.py` exposes `urgency_score`, but it remains `0` during intake.
- `summary_node()` calls the ML urgency classifier.
- `main.py` normalizes a rule-based dashboard score.
- `frontend/src/clinicalState.js` computes its own triage score.

Question selection is therefore not driven by the same triage model the dashboard shows.

## Why Question Quality Degrades

Question quality degrades when the system cannot answer these deterministic questions:

1. What complaint workflow are we in?
2. Which required clinical fields are already known?
3. Which required fields are still missing?
4. Which missing field is highest priority given current risk?
5. Has this field been answered, or merely mentioned?
6. What is the safest concrete fallback if generation fails?

Currently, `question_node()` often asks a weaker substitute question because it routes through:

```text
missing NLICE + concept memory + semantic redundancy + generic fallback
```

instead of:

```text
workflow + structured missing field + risk priority + answer-aware completion
```

## V2 Architectural Direction

SevaCare V2 should make clinical workflow state the primary controller:

```text
Patient message
-> extract structured clinical facts
-> identify complaint workflow
-> compute missing workflow fields
-> choose highest-priority missing field
-> generate one natural question
-> update field-level completion
```

RAG and Gemini can remain phrasing helpers. They should not decide clinical priority.

## Target Responsibility Split

`extract_info_node()`:

- extract structured facts into `clinical_state`;
- keep updating NLICE;
- update workflow key and field completion;
- record evidence for each field.

`question_node()`:

- select workflow;
- choose missing field by priority order;
- use risk overrides;
- avoid repeats;
- return a concrete question.

`concept_memory`:

- remain a repetition guard;
- no longer serve as the source of truth for clinical completion.

`followup_question_agent()` and `clinical_exploration_agent()`:

- remain optional natural-language phrasing layers;
- do not decide which clinical field to ask next.

## Design Principle

The future system should never ask an abstract high-risk question when a concrete missing safety field exists.
