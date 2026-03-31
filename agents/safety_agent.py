def safety_agent(patient_answers: dict):
    """
    Safety Agent

    Responsibility:
    - Identify potential safety risks
    - Flag issues for doctor attention
    - Do NOT make medical decisions
    """

    patient_answers = patient_answers or {}
    safety_flags = []

    # Side effects
    side_effects = patient_answers.get("side_effects", "").lower()
    if side_effects and side_effects not in ["no", "none", "nothing"]:
        safety_flags.append(
            f"Patient reports side effects: {side_effects}"
        )

    # Allergies
    allergies = patient_answers.get("allergies", "").lower()
    if allergies and allergies not in ["no", "none"]:
        safety_flags.append(
            f"Patient reports allergy: {allergies}"
        )

    # Other medicines
    other_meds = patient_answers.get("other_medicines", "").lower()
    if other_meds and other_meds not in ["no", "none"]:
        safety_flags.append(
            f"Patient is taking other medicines: {other_meds}"
        )

    # Chronic conditions
    chronic = patient_answers.get("chronic_conditions", "").lower()
    if chronic and chronic not in ["no", "none"]:
        safety_flags.append(
            f"Patient has chronic condition(s): {chronic}"
        )

    return {
        "safety_flags": safety_flags if safety_flags else ["No immediate safety risks reported"]
    }
