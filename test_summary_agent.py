from agents.summary_agent import summary_agent

state = {
    "complaint": "Body pain and weakness for 5 days",
    "case_type": "Ongoing treatment",
    "vision_output": {
        "vision_output": "Medicine: Paracetamol\nDosage: NOT SURE"
    },
    "patient_answers": {
        "why_prescribed": "Fever",
        "duration": "5 days",
        "response": "Slightly better",
        "side_effects": "Stomach pain",
        "other_medicines": "None"
    },
    "safety_flags": [
        "Patient reports side effects: stomach pain"
    ]
}

result = summary_agent(state)
print("===== DOCTOR SUMMARY =====")
print(result)
