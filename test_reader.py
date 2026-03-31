from agents.reader_agent import vision_reader_agent

with open(r"D:\agentic_healthcare_ai\sample_prescription.jpeg", "rb") as f:
    image_bytes = f.read()

result = vision_reader_agent(image_bytes)

print("===== GEMINI OUTPUT =====")
print(result)
