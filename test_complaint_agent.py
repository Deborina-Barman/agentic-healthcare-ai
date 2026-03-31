from agents.complaint_agent import complaint_agent

patient_input = "I had fever last week, now I feel body pain and weakness, stomach is also upset"

result = complaint_agent(patient_input)

print("===== CLEANED COMPLAINT =====")
print(result)
