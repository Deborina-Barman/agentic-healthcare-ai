from agents.clinical_context_agent import clinical_context_agent

state = {
    "complaint": "Fever and body pain for 5 days",
    "vision_output": {
        "vision_output": "Medicine: Paracetamol\nDosage: NOT SURE"
    },
    "patient_answers": {
        "why_prescribed": "Fever",
        "duration": "5 days",
        "response": "Slightly better",
        "side_effects": "Stomach pain"
    },
    "safety_flags": [
        "Patient reports side effects: stomach pain"
    ]
}

result = clinical_context_agent(state)
print("===== CLINICAL CONTEXT =====")
print(result["clinical_context"])
