# Proposed Clinical State Model

## Goal

SevaCare needs a structured clinical state that separates:

- general complaint information;
- NLICE symptom characterization;
- complaint-specific workflow fields;
- safety/red-flag fields;
- question history and completion metadata.

This lets the system ask:

```text
What clinically important field is missing next?
```

instead of:

```text
What broad concept has not been explored?
```

## Proposed State Shape

```json
{
  "chief_complaint": "",
  "workflow_key": "",
  "nlice": {
    "nature": "",
    "location": "",
    "intensity": "",
    "chronology": "",
    "excitation": ""
  },
  "clinical_fields": {
    "duration": "",
    "onset": "",
    "temperature_max": null,
    "temperature_current": null,
    "temperature_unit": "F",
    "cough": null,
    "sore_throat": null,
    "runny_nose": null,
    "shortness_of_breath": null,
    "wheezing": null,
    "chest_pain": null,
    "palpitations": null,
    "weakness": null,
    "body_aches": null,
    "chills": null,
    "sweating": null,
    "headache": null,
    "vision_changes": null,
    "confusion": null,
    "fainting": null,
    "stiff_neck": null,
    "rash": null,
    "vomiting": null,
    "diarrhea": null,
    "blood_in_stool": null,
    "hydration_status": "",
    "urination_normal": null,
    "medication_taken": "",
    "medication_name": "",
    "medication_dose": "",
    "medication_timing": "",
    "medication_response": "",
    "sick_contacts": null,
    "covid_flu_test": "",
    "travel_or_mosquito_exposure": null,
    "pregnancy_possible": null,
    "last_menstrual_period": "",
    "recent_medication_changes": null,
    "prior_similar_episode": null,
    "cardiac_history": null
  },
  "workflow_progress": {
    "required_fields": [],
    "completed_fields": [],
    "missing_fields": [],
    "last_target_field": "",
    "last_question_intent": "",
    "field_evidence": {}
  },
  "safety": {
    "red_flags_screened": false,
    "red_flags_present": [],
    "red_flags_denied": [],
    "triage_score": 0,
    "triage_level": "Low",
    "triage_reasons": []
  },
  "conversation_control": {
    "questions": [],
    "asked_fields": [],
    "turn_count": 0,
    "conversation_complete": false,
    "concept_memory": {
      "explored": [],
      "uncertain": []
    }
  }
}
```

## Field Semantics

Use `null` for unknown boolean fields:

- `true`: patient confirmed.
- `false`: patient denied.
- `null`: not asked or unclear.

Use strings for fields where free text matters:

- duration;
- medication name;
- medication response;
- hydration status;
- onset pattern.

Use numeric fields for measurements:

- temperature max;
- temperature current;
- pain severity where applicable.

## What Should Remain NLICE

NLICE should remain as a cross-complaint symptom characterization layer.

Keep in NLICE:

- `nature`: quality/character of the main symptom.
- `location`: anatomical area, when relevant.
- `intensity`: patient-rated severity, especially for pain and headache.
- `chronology`: onset/duration/progression summary.
- `excitation`: triggers, relievers, worsening factors.

NLICE is still useful for:

- summary generation;
- ML urgency features if retained;
- generic complaints without a configured workflow;
- doctor-facing compact symptom model.

## What Should Become Structured Fields

Fields should become structured when they affect workflow branching, safety, or completion.

### Fever

Move to structured fields:

- `temperature_max`
- `temperature_current`
- `temperature_unit`
- `medication_taken`
- `medication_name`
- `medication_response`
- `hydration_status`
- `urination_normal`
- `chills`
- `sweating`
- `body_aches`
- `weakness`
- `cough`
- `shortness_of_breath`
- `vomiting`
- `diarrhea`
- `rash`
- `sick_contacts`
- `travel_or_mosquito_exposure`

Reason:

These are not just descriptive symptom qualities. They drive urgency and next-question priority.

### Cough

Move to structured fields:

- `cough_productive`
- `sputum_color`
- `shortness_of_breath`
- `wheezing`
- `fever`
- `chills`
- `sore_throat`
- `nasal_congestion`
- `chest_pain`
- `inhaler_use`
- `inhaler_response`
- `sick_contacts`
- `reflux_or_eating_trigger`

### Headache

Move to structured fields:

- `sudden_onset`
- `worst_headache`
- `vision_changes`
- `confusion`
- `fainting`
- `stiff_neck`
- `fever`
- `nasal_symptoms`
- `medication_response`
- `hydration_status`
- `sleep_impact`

### Chest Pain

Move to structured fields:

- `pressure_or_tightness`
- `shortness_of_breath`
- `radiation_arm_jaw_back`
- `palpitations`
- `dizziness`
- `exertional_trigger`
- `deep_breath_effect`
- `cardiac_history`
- `recent_medication_changes`

### Abdominal Pain

Move to structured fields:

- `abdominal_location`
- `pain_severity`
- `vomiting`
- `diarrhea`
- `constipation`
- `blood_in_stool`
- `dark_stool`
- `fever`
- `hydration_status`
- `urination_normal`
- `food_trigger`
- `diet_change`
- `medication_or_supplement_change`
- `pregnancy_possible`
- `last_menstrual_period`
- `travel_or_sick_contacts`
- `lightheadedness`
- `fall`
- `back_pain`

## Field Evidence

Each structured field should preserve evidence:

```json
{
  "temperature_max": {
    "value": 105,
    "source_turn": 3,
    "source_text": "105",
    "confidence": "high",
    "asked_by_field": "temperature_max"
  }
}
```

This prevents concept-memory errors such as marking severity complete when the patient only provided a temperature.

## Completion Rules

A workflow field is complete only when one of these is true:

- a valid value is extracted;
- the patient clearly denies it;
- the workflow marks it optional and the risk state does not require it.

Asked-but-unanswered is not complete.

Example:

```text
Assistant: Have you taken fever medicine, and did the temperature come down?
Patient: paracetamol
```

Completed:

- `medication_taken`
- `medication_name`

Still missing:

- `medication_response`

## Relationship To Concept Memory

Concept memory should remain, but only as a repetition guard:

- avoid rephrasing the same field too soon;
- detect uncertainty;
- help choose alternate phrasing.

It should not determine whether clinical fields are complete.

## Example Fever State After The Debug Conversation

```json
{
  "chief_complaint": "fever",
  "workflow_key": "fever",
  "nlice": {
    "nature": "fever",
    "location": "Systemic/General",
    "intensity": "",
    "chronology": "3 days",
    "excitation": ""
  },
  "clinical_fields": {
    "duration": "3 days",
    "temperature_max": 105,
    "temperature_unit": "F",
    "cough": true,
    "medication_taken": "paracetamol",
    "medication_response": "",
    "hydration_status": "drinking fluids and urinating normally",
    "urination_normal": true,
    "shortness_of_breath": null,
    "confusion": null,
    "stiff_neck": null,
    "severe_weakness": null,
    "persistent_vomiting": null,
    "diarrhea": null,
    "rash": null,
    "travel_or_mosquito_exposure": null,
    "sick_contacts": null
  },
  "safety": {
    "red_flags_screened": false,
    "triage_level": "High",
    "triage_reasons": ["Very high fever: 105 F", "Respiratory symptom reported"]
  }
}
```

The next target should be `danger_red_flags` or `medication_response`, not a generic follow-up.
