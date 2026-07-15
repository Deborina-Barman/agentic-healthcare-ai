import unittest

from chat_controller import (
    _extract_associated_symptoms,
    _normalize_clinical_summary,
    _priority_followup_question,
    extract_clinical_fields,
    get_missing_workflow_fields,
    get_next_workflow_question,
)


def fever_state(**clinical_fields):
    return {
        "workflow_key": "fever",
        "complaint": "fever",
        "nlice_data": {"chronology": "2 days"},
        "associated_symptoms": [],
        "clinical_fields": {
            "duration": "2 days",
            "temperature_max": 104,
            "associated_respiratory_symptoms": False,
            "associated_systemic_symptoms": False,
            "hydration_status": "drinking fluids",
            "vomiting": False,
            "diarrhea": False,
            "danger_red_flags": False,
            "sick_contacts": False,
            **clinical_fields,
        },
        "red_flags_screened": True,
        "questions": [],
        "concept_memory": {},
    }


class ClinicalStateRefactorTests(unittest.TestCase):
    def test_negated_symptoms_are_false_fields(self):
        text = "No chest pain, no vomiting, no rash, no confusion."

        self.assertEqual(_extract_associated_symptoms(text), [])

        fields = extract_clinical_fields(
            state={"clinical_fields": {}},
            user_text=text,
            latest_ai_text="",
            nlice_data={},
            associated_symptoms=[],
            medications=None,
        )

        self.assertFalse(fields["chest_pain"])
        self.assertFalse(fields["vomiting"])
        self.assertFalse(fields["rash"])
        self.assertFalse(fields["confusion"])

    def test_mixed_positive_and_negative_symptoms(self):
        text = "I have cough but no chest pain."
        symptoms = _extract_associated_symptoms(text)
        fields = extract_clinical_fields(
            state={"clinical_fields": {}},
            user_text=text,
            latest_ai_text="",
            nlice_data={},
            associated_symptoms=symptoms,
            medications=None,
        )

        self.assertIn("cough", symptoms)
        self.assertNotIn("chest pain", symptoms)
        self.assertTrue(fields["cough"])
        self.assertFalse(fields["chest_pain"])

    def test_fever_workflow_asks_medication_taken_first(self):
        state = fever_state(
            medication_taken=None,
        )
        state["clinical_fields"].pop("medication_taken", None)

        field, question = get_next_workflow_question(state)

        self.assertEqual(field, "medication_taken")
        self.assertIn("taken any fever medicine", question)

    def test_medication_response_skipped_when_no_medicine_taken(self):
        state = fever_state(medication_taken=False)

        missing = get_missing_workflow_fields(state)

        self.assertNotIn("medication_response", missing)

    def test_high_risk_chest_pain_and_breathing_promotes_escalation(self):
        state = {
            "complaint": "cough",
            "associated_symptoms": ["chest pain", "breathing difficulty"],
            "clinical_fields": {
                "chest_pain": True,
                "breathing_difficulty": True,
            },
            "questions": [],
            "concept_memory": {},
        }

        concept, question = _priority_followup_question(state)

        self.assertEqual(concept, "cardiac_red_flags")
        self.assertIn("chest pain and breathing difficulty", question)

    def test_summary_separates_denied_symptoms(self):
        summary = _normalize_clinical_summary(
            {
                "complaint": "fever",
                "age_gender": "Patient",
                "associated_symptoms": ["cough"],
                "clinical_fields": {
                    "chest_pain": False,
                    "vomiting": False,
                },
                "nlice_data": {"chronology": "2 days"},
                "messages": [],
            }
        )

        self.assertIn("associated with cough", summary)
        self.assertIn("denies chest pain and vomiting", summary)


if __name__ == "__main__":
    unittest.main()
