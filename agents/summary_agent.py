def summary_agent(state: dict) -> str:
    """
    Generate a structured, professional, non-diagnostic clinical summary
    using the outputs collected across the intake pipeline.
    """
    age_gender = state.get("age_gender") or "Not specified"
    complaint = state.get("complaint") or "Not specified"
    patient_answers = state.get("patient_answers") or {}
    medications = state.get("medications") or "Not reported"
    allergies = state.get("allergies") or "Not reported"
    past_history = state.get("past_history") or "Not reported"
    urgency = state.get("urgency") or "Low"
    clinical_context = state.get("clinical_context") or "Clinical context not available."

    symptom_lines = []
    for question, answer in patient_answers.items():
        if answer and str(answer).strip():
            symptom_lines.append(f"- {question}: {answer}")

    summary = []

    summary.append("## Clinical Case Summary")
    summary.append("")
    summary.append("### Urgency Level")
    summary.append(f"- {urgency}")
    summary.append("")

    summary.append("### S - Subjective")
    summary.append(f"- Patient demographics: {age_gender}")
    summary.append(f"- Chief complaint: {complaint}")
    if symptom_lines:
        summary.append("- Key symptoms from patient answers:")
        summary.extend(symptom_lines)
    else:
        summary.append("- Key symptoms from patient answers: No additional symptom details were recorded.")
    summary.append("")

    summary.append("### O - Objective")
    summary.append("- Findings are based on patient-reported data collected during intake.")
    summary.append("- No direct physical examination, vital signs, imaging, or laboratory testing are included here.")
    summary.append("- This report has important limitations because it is based on reported history only.")
    summary.append("")

    summary.append("### A - Assessment (Non-diagnostic)")
    summary.append(f"- General clinical impression: {clinical_context}")
    summary.append("- The overall symptom pattern may require clinical review depending on severity, persistence, and associated features.")
    summary.append("- Uncertainty remains because this summary does not establish a diagnosis.")
    summary.append("")

    summary.append("### P - Plan")
    summary.append("- Continue monitoring symptom progression, severity, and any new associated symptoms.")
    if str(urgency).lower() in {"high", "emergency"}:
        summary.append("- Seek prompt in-person medical evaluation based on the reported urgency level.")
    elif str(urgency).lower() == "moderate":
        summary.append("- Seek medical review if symptoms persist, worsen, or interfere more with normal activity.")
    else:
        summary.append("- Seek medical help if symptoms worsen, do not improve, or new concerning features appear.")
    summary.append("- This summary does not provide treatment or medication instructions.")
    summary.append("")

    summary.append("### Additional History")
    summary.append(f"- Medications: {medications}")
    summary.append(f"- Allergies: {allergies}")
    summary.append(f"- Past conditions: {past_history}")
    summary.append("")

    summary.append("### Disclaimer")
    summary.append("- This is an AI-assisted clinical intake summary and is not a diagnosis.")
    summary.append("- It does not prescribe medicines or replace professional medical judgment.")
    summary.append("- Final clinical decisions must be made by a qualified healthcare professional.")

    return "\n".join(summary)
