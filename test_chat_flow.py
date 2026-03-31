from chat_controller import ChatController

# Simulate chat
chat = ChatController()

print(chat.handle_text("I have body pain and fever for 5 days"))

print(chat.handle_text("Ongoing treatment"))

# Simulate prescription upload
with open("sample_prescription.jpeg", "rb") as f:
    image_bytes = f.read()

questions = chat.handle_file(image_bytes)
print("\nQuestions for patient:")
for q in questions:
    print("-", q)

# Simulate patient answers
patient_answers = {
    "why_prescribed": "Fever",
    "duration": "5 days",
    "response": "Slightly better",
    "side_effects": "Stomach pain",
    "other_medicines": "None",
    "allergies": "No",
    "chronic_conditions": "No"
}

print(chat.run_safety_check(patient_answers))

summary = chat.generate_summary()
print("\n===== DOCTOR SUMMARY =====")
print(summary)
