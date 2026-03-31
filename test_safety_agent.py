from agents.safety_agent import safety_agent

patient_answers = {
    "side_effects": "stomach pain",
    "allergies": "penicillin",
    "other_medicines": "painkiller daily",
    "chronic_conditions": "diabetes"
}

result = safety_agent(patient_answers)

print("===== SAFETY FLAGS =====")
for flag in result["safety_flags"]:
    print("-", flag)
