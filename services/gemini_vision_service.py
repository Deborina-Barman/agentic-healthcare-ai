import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image
import io

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def read_prescription_with_gemini(image_bytes: bytes) -> str:
    try:
        image_part = types.Part.from_bytes(
            data=image_bytes,
            mime_type="image/jpeg"
        )

        prompt = (
            "You are reading a handwritten medical prescription.\n\n"
            "Rules:\n"
            "- List ONLY what you can clearly read.\n"
            "- If a word, medicine name, or dosage is unclear, write: NOT SURE.\n"
            "- Do NOT guess medicine names.\n"
            "- Do NOT guess diagnosis.\n"
            "- Do NOT infer disease or condition.\n"
            "- Be honest and cautious.\n"
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[image_part, prompt],
        )

        return response.text if response.text else "NOT SURE"

    except Exception as e:
        return f"ERROR: {str(e)}"
