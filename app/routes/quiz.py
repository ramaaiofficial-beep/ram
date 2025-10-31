from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import requests
import json

router = APIRouter()

API_KEY = 'AIzaSyAQZRsBJZg40AG208w_pVou0_OISnytYGY'  # Replace with your actual API key
ENDPOINT = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent'

HEADERS = {
    'Content-Type': 'application/json',
    'X-Goog-Api-Key': API_KEY
}

class QuizRequest(BaseModel):
    topic: str

@router.post("/generate")
async def generate_quiz(request: QuizRequest):
    prompt = f"""
    Generate 5 multiple-choice questions on the topic "{request.topic}".
    Each question must include:
    - A question string
    - Exactly 4 options (A, B, C, D)
    - One correct answer

    Format the response strictly as a JSON array like this:
    [
      {{
        "question": "What is ...?",
        "options": ["Option A", "Option B", "Option C", "Option D"],
        "correct_answer": "Option B"
      }},
      ...
    ]
    """

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }

    response = requests.post(ENDPOINT, headers=HEADERS, json=payload)

    if response.status_code == 200:
        try:
            content = response.json()['candidates'][0]['content']['parts'][0]['text']

            start = content.find("[")
            end = content.rfind("]") + 1
            json_str = content[start:end]

            quiz_data = json.loads(json_str)
            return {"questions": quiz_data}

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Parsing error: {str(e)}")
    else:
        raise HTTPException(status_code=500, detail=f"API error: {response.text}")
