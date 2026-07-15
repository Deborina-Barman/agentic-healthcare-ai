# Followup-Q Dataset Analysis

This report analyzes `data/followupq.csv` to identify symptom-specific clinical questioning patterns for SevaCare AI.

## Dataset Inspection

Dataset shape:

- Rows: 250
- Columns: 3

Columns discovered:

| Column | Role |
|---|---|
| `EHR` | Patient background, demographics, problems, recent encounters, and medications |
| `Message` | Patient complaint/message text |
| `Questions` | Clinician-authored follow-up questions |

The analysis uses `Message` as the patient complaint column and `Questions` as the follow-up question column.

Important method note: complaint matching was performed against `Message`, not `EHR`, because the EHR column contains historical diagnoses that can mention unrelated symptoms. Negated mentions such as "I do not have a fever" were filtered from the fever workflow.

## Semantic Grouping Method

The `Questions` field is stored as a string representation of a question array. Questions were extracted from quoted strings, normalized for whitespace, and grouped by recurring clinical intent. The groups are semantic buckets such as:

- `duration_onset`
- `severity_intensity`
- `associated_respiratory`
- `associated_gi`
- `associated_systemic`
- `medication_response`
- `trigger_pattern`
- `exposure_infection`
- `cardiac_red_flags`
- `neuro_red_flags`
- `hydration_urination`
- `pregnancy_gyne`
- `history_recurrence`

These group labels are names for the observed question patterns. The counts come from the CSV.

## Fever Workflow

Dataset evidence:

- Matching cases: 5
- Extracted follow-up questions: 57

Required information doctors commonly try to collect:

- Duration/onset of fever
- Temperature height and measurement method
- Systemic symptoms such as chills, fatigue, body aches, shaking
- Respiratory symptoms such as sore throat, cough, congestion, shortness of breath
- Medication or OTC response
- COVID/flu or recent infectious exposure
- Chest pain, palpitations, or breathing red flags
- GI symptoms when present

Semantic question-group frequencies:

| Group | Count |
|---|---:|
| associated_systemic | 11 |
| associated_respiratory | 10 |
| severity_intensity | 5 |
| medication_response | 5 |
| cardiac_red_flags | 5 |
| duration_onset | 5 |
| associated_gi | 3 |
| exposure_infection | 2 |
| trigger_pattern | 2 |
| history_recurrence | 2 |
| neuro_red_flags | 1 |
| other | 15 |

Most common/evidence-bearing questions:

- "How high are the temperatures you are measuring at home and how are you measuring them?"
- "How high is your fever?"
- "Exactly how long have you had the fever?"
- "When did symptoms first begin?"
- "What medicine are you taking to control your fever and how much/often?"
- "Are you treating the fever with any over the counter medications?"
- "Have you taken any OTC medications for your fever and have they worked?"
- "Do you have any chills?"
- "Any sore throat?"
- "Any cough?"
- "Any shortness or breath"
- "Have you tested positive for COVID or flu?"
- "Do you have any chest pain?"
- "Any palpitations?"
- "Do you have any liquid stools?"

Recommendation for SevaCare:

For fever, ask temperature and duration early, then screen systemic/respiratory symptoms and medication response. If chest tightness, shortness of breath, palpitations, or severe systemic symptoms appear, escalate to red-flag screening.

## Cough Workflow

Dataset evidence:

- Matching cases: 9
- Extracted follow-up questions: 95

Required information doctors commonly try to collect:

- Duration/onset
- Cough type and production: dry/productive, mucus, phlegm, sputum
- Shortness of breath, wheezing, and ability to catch breath
- Fever, chills, body aches
- Nasal congestion, sore throat, post-nasal symptoms
- Medication, OTC, or inhaler use and response
- Recent illness, sick contacts, COVID/flu exposure
- Chest pain or palpitations
- Reflux/eating-related cough triggers

Semantic question-group frequencies:

| Group | Count |
|---|---:|
| associated_respiratory | 17 |
| associated_systemic | 16 |
| exposure_infection | 8 |
| trigger_pattern | 8 |
| associated_gi | 7 |
| duration_onset | 7 |
| medication_response | 7 |
| cardiac_red_flags | 7 |
| neuro_red_flags | 6 |
| history_recurrence | 4 |
| hydration_urination | 1 |
| severity_intensity | 1 |
| other | 23 |

Most common/evidence-bearing questions:

- "How long have your symptoms been going on?"
- "When did your symptoms first start?"
- "Do you have a fever?"
- "Have you had any fever?"
- "Do you have any chills?"
- "Are you having trouble catching your breath?"
- "Do you have any shortness of breath?"
- "Have you been wheezing?"
- "Are you coughing up any food?"
- "If you are using your inhaler, is it helping?"
- "Have you treated your symptoms with any medications?"
- "Have you been in contact with anyone who is sick?"
- "Are you having any chest pain?"
- "Any new or abnormal palpitations?"
- "Is your GERD worse after eating?"

Recommendation for SevaCare:

For cough, first separate uncomplicated cough from respiratory risk by asking duration, fever/chills, shortness of breath, wheeze, and sputum/productive character. Add inhaler/medication response for patients with asthma-like or wheezing language, and ask reflux/eating triggers when cough is meal-related.

## Headache Workflow

Dataset evidence:

- Matching cases: 6
- Extracted follow-up questions: 47

Required information doctors commonly try to collect:

- Duration/onset
- Pain severity
- Sinus/nasal/respiratory symptoms
- Fever, chills, body aches
- Vision or neurologic symptoms
- Medication response
- COVID/flu or recent illness exposure
- Hydration, sleep, and skipped meals
- Progression pattern or worsening after initial improvement

Semantic question-group frequencies:

| Group | Count |
|---|---:|
| associated_respiratory | 9 |
| associated_systemic | 7 |
| exposure_infection | 5 |
| duration_onset | 4 |
| medication_response | 3 |
| severity_intensity | 3 |
| trigger_pattern | 2 |
| neuro_red_flags | 2 |
| hydration_urination | 1 |
| other | 14 |

Most common/evidence-bearing questions:

- "How long have you had this sinus pain?"
- "How long have the symptoms been going on?"
- "Do you have a headache if so how painful on 0-10 pain scale? 10 being the most pain."
- "Any fevers?"
- "Do you have any chills?"
- "Have you had any bodyaches?"
- "Are you having any vision issues?"
- "Are you draining any boogers or coughing up any phlegm"
- "Do you have any cough?"
- "Do you have any shortness of breath?"
- "Have you tried any medications for the sinus pain?"
- "Have you tested for covid or the flu at home?"
- "Were you recently sick?"
- "Have you been hydrating?"
- "Is the pain affecting your sleep?"

Recommendation for SevaCare:

The headache evidence in this CSV is often sinus-associated. SevaCare should ask onset, severity, fever, nasal symptoms, cough, and medication response, while preserving a red-flag branch for vision changes, dizziness, sudden severe headache, confusion, fainting, or neurologic symptoms.

## Chest Pain Workflow

Dataset evidence:

- Matching cases: 4
- Extracted follow-up questions: 40

Required information doctors commonly try to collect:

- Duration/onset
- Chest pain, pressure, or tightness character
- Shortness of breath and deep-breath effect
- Palpitations
- Radiation to arm, back, jaw, or abdomen
- Dizziness/lightheadedness
- Fever, chills, cough, sore throat
- Trigger or worsening pattern
- Prior similar episode or cardiac history
- Recent medication changes

Semantic question-group frequencies:

| Group | Count |
|---|---:|
| associated_respiratory | 8 |
| cardiac_red_flags | 7 |
| associated_systemic | 6 |
| trigger_pattern | 5 |
| associated_gi | 3 |
| duration_onset | 3 |
| history_recurrence | 2 |
| medication_response | 2 |
| neuro_red_flags | 2 |
| severity_intensity | 1 |
| other | 5 |

Most common/evidence-bearing questions:

- "Any shortness of breath?"
- "Can you take a deep breath?"
- "Any cough?"
- "Do you have any chest pain?"
- "Do you have any chest pressure?"
- "Have you have any palpitations?"
- "Any chest palpitations?"
- "Any pain in your arms?"
- "Are you experiencing any jaw, arm, abdominal or back pain?"
- "Are you dizzy/lightheaded?"
- "How long have you been experiencing these symptoms?"
- "When did your symptoms start?"
- "Is there anything that triggers the tightness?"
- "Have you ever had anything like this happen to you before?"
- "Any recent changes to your medication? E.g. missed doses in past week, or inability to pick them up"

Recommendation for SevaCare:

Chest pain should remain a high-priority branch. The dataset questions focus on breathing symptoms, chest pressure/palpitations, radiation, dizziness, duration, triggers, and history. SevaCare should ask these before generic NLICE completion and should surface urgent triage alerts when chest pain coexists with shortness of breath, radiation, palpitations, or dizziness.

## Abdominal Pain Workflow

Dataset evidence:

- Matching cases: 56
- Extracted follow-up questions: 517

Required information doctors commonly try to collect:

- Duration/onset
- Pain location and intensity
- Nausea, vomiting, diarrhea, constipation
- Bowel habit or stool changes
- Blood in stool or dark stool
- Fever, chills, body aches
- Hydration or urination changes
- Diet, food, or after-eating pattern
- Medication or supplement use
- Pregnancy or menstrual context
- Travel, sick contacts, or infectious exposure
- Chest pain, breathing difficulty, and back pain red flags
- Weight loss and recurrence history

Semantic question-group frequencies:

| Group | Count |
|---|---:|
| associated_gi | 123 |
| associated_systemic | 57 |
| duration_onset | 43 |
| trigger_pattern | 42 |
| medication_response | 41 |
| cardiac_red_flags | 27 |
| exposure_infection | 26 |
| neuro_red_flags | 22 |
| pregnancy_gyne | 17 |
| hydration_urination | 17 |
| associated_respiratory | 17 |
| history_recurrence | 15 |
| severity_intensity | 5 |
| other | 126 |

Most common/evidence-bearing questions:

- "Do you have a fever?"
- "How long have your symptoms been going on?"
- "Are you having any abdominal pain?"
- "Where are you feeling the abdominal pain?"
- "What level of pain 0-10 when you are experiencing your symptoms?"
- "Have you vomited?"
- "Any changes in your bowel habits?"
- "Is there blood in your stools?"
- "Is your stool entirely liquid?"
- "Does your stool have a new, distinctly awful smell?"
- "Are your symptoms getting better, worse or staying the same?"
- "Are you on a new diet?"
- "Have you started any new medications or supplements?"
- "Are you currently pregnant?"
- "When was your last menstrual period?"
- "Do you feel lightheaded?"
- "Have you fallen?"
- "Have you had any chest pain?"
- "Any back pain?"
- "Have you travelled out of the country recently?"

Recommendation for SevaCare:

Abdominal pain has the strongest evidence in this dataset. The workflow should collect GI symptoms first, then fever/systemic symptoms, duration, food/diet triggers, medication/supplement changes, pregnancy/menstrual context where relevant, hydration/urination, and red flags such as chest pain, back pain, lightheadedness, falls, blood in stool, and weight loss.

## Integration Recommendations for SevaCare AI

1. Add `clinical_workflows.py` as a deterministic workflow layer before calling Gemini.

2. In `chat_controller.py`, map complaint text to a workflow key:

```python
from clinical_workflows import get_workflow

workflow = get_workflow(state.get("complaint") or "")
required_fields = workflow.get("required_fields", [])
```

3. Store workflow progress in state, for example:

```python
state["workflow_key"] = "fever"
state["workflow_fields_collected"] = {
    "duration_onset": True,
    "temperature_severity": False,
}
```

4. Use the workflow layer to select a clinical intent before question generation. The LLM should phrase the question, but deterministic code should decide the missing intent.

5. Keep the existing RAG agent as the phrasing enhancer:

```text
complaint + workflow target + previous questions
  -> retrieve similar Followup-Q examples
  -> Gemini asks one clinician-style question
```

6. Add priority overrides for high-risk workflows:

- Chest pain: breathing difficulty, radiation, palpitations, dizziness.
- Fever: high temperature, shortness of breath, chest pain, severe weakness.
- Abdominal pain: blood in stool, dehydration, pregnancy context, severe pain, lightheadedness/falls.

7. Use dataset frequencies to order questions:

- For abdominal pain, GI questions should come before lower-frequency severity questions.
- For cough, respiratory/systemic questions should come before reflux triggers unless the complaint mentions eating or GERD.
- For headache, sinus/respiratory context is common in this dataset, but red-flag neurologic screening should still be available as a safety branch.

## Current Limitations of This Analysis

- The dataset has only 250 rows.
- Chest pain and fever had few primary-complaint matches, so their workflows should be treated as seed workflows, not final clinical protocols.
- Semantic grouping used transparent keyword rules over clinician questions; it did not use an embedding clustering model.
- The dataset questions contain typos and inconsistent wording. `clinical_workflows.py` preserves representative questions but SevaCare should clean phrasing before showing patients.
- This analysis is for clinical intake support and does not create diagnostic or treatment rules.
