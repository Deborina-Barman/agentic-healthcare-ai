# Question Selection Plan

## Purpose

The V2 question selector should use deterministic workflow state to decide what clinical information is missing, then use natural-language generation only to phrase that selected intent.

It should not ask a generic follow-up when a concrete workflow field is missing.

## Current Flow

Current `question_node()` roughly does this:

```text
missing NLICE fields
-> _select_question_focus()
-> maybe _priority_followup_question()
-> maybe clinical_exploration_agent()
-> maybe followup_question_agent()
-> static fallback
```

Current control signals:

- `nlice_data`
- `associated_symptoms`
- `red_flags_screened`
- `questions`
- `exploration_questions`
- `concept_memory`
- `_has_high_fever()`
- semantic redundancy checks

Current problem:

The selector can know the case is high risk without knowing which high-risk field is still missing. This is how it falls through to:

```text
Can you share one more detail about the higher-risk symptom pattern?
```

## Future Flow

Future selection should be:

```text
chief complaint
-> workflow key
-> workflow required fields
-> extracted structured clinical state
-> missing required fields
-> risk overrides
-> selected target field
-> concrete question template or phrased question
-> update field evidence on next turn
```

## Pseudo-Flow

```python
def select_next_question(state):
    workflow = get_workflow(state["workflow_key"] or state["chief_complaint"])
    clinical_state = state["clinical_fields"]

    missing = find_missing_workflow_fields(
        workflow=workflow,
        clinical_fields=clinical_state,
        field_evidence=state["workflow_progress"]["field_evidence"],
    )

    risk_promoted = apply_conditional_priority(
        workflow=workflow,
        clinical_fields=clinical_state,
        missing_fields=missing,
        safety=state["safety"],
    )

    target_field = first_unanswered_field(
        priority_order=risk_promoted or workflow["priority_order"],
        missing_fields=missing,
        asked_fields=state["workflow_progress"]["asked_fields"],
        concept_memory=state["concept_memory"],
    )

    if not target_field:
        if nlice_missing_for_generic_summary(state):
            target_field = select_remaining_nlice_field(state)
        else:
            return complete_intake()

    question = workflow["field_questions"].get(target_field)
    if not question:
        question = safe_static_question_for_field(target_field)

    return {
        "target_field": target_field,
        "question": question,
        "source": "workflow",
    }
```

## Field Completion

A field should be considered complete only when it has valid evidence.

Complete examples:

- `temperature_max = 105`
- `cough = true`
- `vomiting = false`
- `hydration_status = "drinking fluids and urinating normally"`

Not complete:

- field was asked but patient answered vaguely;
- concept memory contains related keyword;
- a multi-part question was partially answered.

Example:

```text
Assistant: Have you taken fever medicine, and did the temperature come down?
Patient: paracetamol
```

Complete:

- `medication_taken`
- `medication_name`

Missing:

- `medication_response`

## Risk Overrides

Risk overrides should promote fields, not generate vague questions.

Example fever state:

```json
{
  "temperature_max": 105,
  "cough": true,
  "medication_taken": "paracetamol",
  "hydration_status": "ok"
}
```

Promoted missing fields:

1. `danger_red_flags`
2. `medication_response`
3. `vomiting_diarrhea`
4. `exposure_infection`

Question:

```text
With this fever, are you having trouble breathing, confusion, stiff neck, severe weakness, persistent vomiting, chest pain, fainting, rash, or signs of dehydration?
```

## Role Of Concept Memory

Concept memory should remain in the selector, but only for:

- duplicate prevention;
- alternate phrasing after uncertainty;
- avoiding repeated questions when the field is already complete.

Concept memory should not decide:

- whether `medication_response` is complete;
- whether `red_flags_screened` is complete;
- whether a high-risk workflow can end.

## Role Of NLICE

NLICE should become secondary in configured workflows.

Use NLICE:

- when no complaint workflow exists;
- to enrich summary and dashboard;
- for generic symptom characterization after workflow safety fields are complete.

For configured workflows, workflow fields should lead.

Example:

- Fever should ask `temperature_max` before NLICE `intensity`.
- Chest pain should ask radiation and shortness of breath before generic `excitation`.
- Abdominal pain should ask vomiting/bowel/blood/hydration before generic trigger questions.

## Role Of RAG And LLMs

Do not add more RAG.

RAG/Gemini can stay as optional phrasing helpers:

```text
workflow target field + clinical state + previous questions
-> natural language phrasing
```

But the target field must be chosen deterministically first.

If generation fails, fallback must be the workflow field question, not a generic abstract question.

## Completion Decision

Future completion:

```text
required workflow fields complete
AND high-risk promoted fields complete
AND red flags screened or explicitly not required
AND minimum NLICE summary fields available
```

Do not complete because:

- max question count reached;
- concept memory has broad coverage;
- two exploration questions were asked.

Loop protection can still exist, but it should end with:

- "Clinical intake complete" only if minimum safety fields are done;
- otherwise a concrete safe handoff summary.

## Fever Example In V2

After:

```text
duration = 3 days
cough = true
temperature_max = 105
medication_taken = paracetamol
hydration_status = ok
```

Missing:

- `danger_red_flags`
- `medication_response`
- `vomiting_diarrhea`
- `exposure_infection`

Chosen next target:

- `danger_red_flags`

Chosen question:

```text
With this fever, are you having trouble breathing, confusion, stiff neck, severe weakness, persistent vomiting, chest pain, fainting, rash, or signs of dehydration?
```

This is workflow-driven, specific, and clinically safer.
