# from agents.question_agent import patient_question_agent

# vision_output = "Medicine: Paracetamol\nDosage: NOT SURE"

# result = patient_question_agent(vision_output)

# print("===== QUESTIONS FOR PATIENT =====")
# for q in result["questions"]:
#     print("-", q)
from agents.question_agent import patient_question_agent

print(
    patient_question_agent(
        complaint="I have fever",
        age_gender="24, Female"
    )
)
