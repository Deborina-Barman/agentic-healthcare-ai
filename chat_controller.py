from agents.complaint_agent import complaint_agent
from agents.reader_agent import vision_reader_agent
from agents.question_agent import patient_question_agent
from agents.clinical_synthesis_agent import clinical_synthesis_agent
from agents.urgency_classifier_agent import urgency_classifier_agent
from agents.clinical_context_agent import clinical_context_agent
from agents.summary_agent import summary_agent


class ChatController:
    def __init__(self):
        self.state = {
            "step": "demographics",
            "age_gender": None,
            "complaint": None,
            "duration": None,
            "case_type": None,
            "vision_output": None,
            "questions": [],
            "current_question_index": 0,
            "patient_answers": {},
            "medications": None,
            "allergies": None,
            "past_history": None,
            "nlice": None,
            "urgency": None,
            "clinical_context": None,
            "summary": None
        }

    # ---------------- TEXT INPUT HANDLER ----------------
    def handle_text(self, user_text: str):
        step = self.state["step"]

        # Complaint
        if step == "complaint":
            self.state["complaint"] = complaint_agent(user_text)
            self.state["step"] = "duration"
            return "How many days have you had this problem?"

        # Duration
        elif step == "duration":
            self.state["duration"] = user_text
            self.state["step"] = "context"
            return "Is this your first visit or ongoing treatment?"

        # Context → START QUESTIONS
        elif step == "context":
            self.state["case_type"] = user_text

            questions_data = patient_question_agent(
                complaint=self.state["complaint"],
                age_gender=self.state.get("age_gender")
            )

            self.state["questions"] = questions_data["questions"]
            self.state["current_question_index"] = 0
            self.state["step"] = "clarification"

            total = len(self.state["questions"])
            return f"Question 1 of {total}:\n{self.state['questions'][0]}"

        # Clarification Questions
        elif step == "clarification":
            idx = self.state["current_question_index"]
            question = self.state["questions"][idx]

            self.state["patient_answers"][question] = user_text
            self.state["current_question_index"] += 1

            if self.state["current_question_index"] < len(self.state["questions"]):
                total = len(self.state["questions"])
                current = self.state["current_question_index"] + 1
                next_question = self.state["questions"][self.state["current_question_index"]]
                return f"Question {current} of {total}:\n{next_question}"

            self.state["step"] = "medications"
            return "Are you currently taking any regular medications?"

        # Medications
        elif step == "medications":
            self.state["medications"] = user_text
            self.state["step"] = "allergies"
            return "Do you have any known allergies?"

        # Allergies
        elif step == "allergies":
            self.state["allergies"] = user_text
            self.state["step"] = "past_history"
            return "Do you have any chronic medical conditions?"

        # Past History
        elif step == "past_history":
            self.state["past_history"] = user_text
            self.state["step"] = "summary"
            return "Thank you. I’m preparing the summary for the doctor."

        return "Please wait."

    # ---------------- FILE HANDLER ----------------
    def handle_file(self, image_bytes: bytes):
        self.state["vision_output"] = vision_reader_agent(image_bytes)

    # ---------------- SUMMARY ----------------
    def generate_summary(self):
        # Multi-agent pipeline:
        # User -> Questions -> Answers -> NLICE -> ML Urgency -> Clinical Context -> Summary
        synthesis_result = clinical_synthesis_agent(
            {
                "complaint": self.state["complaint"],
                "age_gender": self.state["age_gender"],
                "patient_answers": self.state["patient_answers"],
            }
        )
        self.state["nlice"] = synthesis_result.get("nlice", {})

        urgency_result = urgency_classifier_agent(
            {
                "complaint": self.state["complaint"],
                "nlice": self.state["nlice"],
            }
        )
        self.state["urgency"] = urgency_result.get("urgency_level", "Low").title()

        clinical_context_result = clinical_context_agent(
            {
                "complaint": self.state["complaint"],
                "nlice": self.state["nlice"],
                "vision_output": self.state["vision_output"],
                "safety_flags": self.state["urgency"],
            }
        )
        self.state["clinical_context"] = clinical_context_result.get(
            "clinical_context", "Clinical context not available."
        )

        self.state["summary"] = summary_agent(self.state)
        self.state["step"] = "done"
        return self.state["summary"]
