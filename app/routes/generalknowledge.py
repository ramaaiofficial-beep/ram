from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query
from pydantic import BaseModel
from app.routes.auth import get_current_user
import requests
import PyPDF2
import io
import base64
import logging
import json

# Router
router = APIRouter(prefix="/general-knowledge", tags=["general-knowledge"])

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class AskBody(BaseModel):
    question: str


# Gemini credentials (same as chat.py)
GEMINI_API_KEY = "AIzaSyCTlQNa7p7sN6VvBaIXK-IOqoBPa7sduro"
GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash:generateContent"
)

headers = {
    "Content-Type": "application/json",
    "X-Goog-Api-Key": GEMINI_API_KEY,
}


def ask_gemini(prompt: str) -> str:
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        response = requests.post(GEMINI_ENDPOINT, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Gemini API error: {e}")


# --- Simple in-memory store (user-wide, no elder scoping) ---
file_store: dict[str, dict[str, str]] = {
    "docs": {},  # key: user_id:filename -> text
}

def extract_pdf_text(file_bytes: bytes, filename: str) -> str:
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
    except Exception:
        raise HTTPException(status_code=400, detail=f"Failed to read '{filename}' as PDF.")
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    if not text.strip():
        raise HTTPException(status_code=400, detail=f"'{filename}' contains no readable text.")
    return text

def call_gemini_with_image(image_bytes: bytes, mime_type: str, instruction: str) -> str:
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": instruction},
                    {"inline_data": {"mime_type": mime_type, "data": b64}},
                ]
            }
        ]
    }
    try:
        response = requests.post(GEMINI_ENDPOINT, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Gemini Vision error: {e}")


@router.post("/upload/docs")
async def upload_doc(file: UploadFile = File(...), user=Depends(get_current_user)):
    user_id = str(user["id"])
    allowed = {"application/pdf", "image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Only PDF or image (jpg/png/webp) allowed.")

    content = await file.read()
    if file.content_type == "application/pdf":
        text = extract_pdf_text(content, file.filename)
    else:
        text = call_gemini_with_image(
            content,
            file.content_type,
            "Extract readable text and key points from this image."
        )

    file_store["docs"][f"{user_id}:{file.filename}"] = text
    logger.info(f"GeneralKnowledge: stored '{file.filename}' for user {user_id}")
    return {"message": f"Uploaded '{file.filename}'"}


@router.post("/ask")
def ask(body: AskBody, filename: str | None = Query(None), user=Depends(get_current_user)):
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Question is required")
    user_id = str(user["id"])

    context = ""
    if filename:
        key = f"{user_id}:{filename}"
        context = file_store["docs"].get(key, "")

    prompt = body.question if not context else f"Context from '{filename}':\n\n{context[:12000]}\n\nQuestion: {body.question}"
    answer = ask_gemini(prompt)
    return {"answer": answer}


@router.get("/quiz")
def generate_quiz(filename: str = Query(...), num: int = Query(10, ge=1, le=20), user=Depends(get_current_user)):
    user_id = str(user["id"])
    key = f"{user_id}:{filename}"
    context = file_store["docs"].get(key, "")
    if not context:
        raise HTTPException(status_code=404, detail="No context found for this file")

    instruction = f"""
From the following study material, create {num} multiple-choice questions for students.
Return STRICT JSON only with this exact schema (no prose):
{{"questions":[{{"question":"...","options":["A","B","C","D"],"answerIndex":0}}]}}
Ensure each question has exactly 4 distinct options and a correct answerIndex 0-3.

Material:\n\n{context[:12000]}
"""

    raw = ask_gemini(instruction)
    # Try to extract JSON
    try:
        # Find first '{' and last '}' to be safe
        start = raw.find('{')
        end = raw.rfind('}')
        candidate = raw[start:end+1] if start != -1 and end != -1 else raw
        data = json.loads(candidate)
        # Basic validation
        questions = data.get("questions", [])
        cleaned = []
        for q in questions:
            opts = q.get("options", [])
            if isinstance(opts, list) and len(opts) == 4 and isinstance(q.get("answerIndex", 0), int):
                cleaned.append({
                    "question": q.get("question", ""),
                    "options": opts,
                    "answerIndex": max(0, min(3, q.get("answerIndex", 0)))
                })
        if not cleaned:
            raise ValueError("No valid questions parsed")
        return {"questions": cleaned}
    except Exception as e:
        logger.error(f"Quiz JSON parse failed: {e}; raw=\n{raw}")
        raise HTTPException(status_code=502, detail="Failed to generate quiz JSON")


@router.get("/links")
def relevant_links(filename: str = Query(...), num: int = Query(5, ge=1, le=10), user=Depends(get_current_user)):
    """Generate YouTube search topics relevant to the uploaded doc and return clickable search URLs."""
    user_id = str(user["id"])
    key = f"{user_id}:{filename}"
    context = file_store["docs"].get(key, "")
    if not context:
        raise HTTPException(status_code=404, detail="No context found for this file")

    instruction = f"""
From the material below, list {num} concise YouTube search topics a student should watch to learn this content better.
Return STRICT JSON only as: {{"topics":[{{"title":"...","query":"..."}}]}}
Keep each query under 8 words; do not include URLs.

Material:\n\n{context[:8000]}
"""

    raw = ask_gemini(instruction)
    try:
        start = raw.find('{'); end = raw.rfind('}')
        candidate = raw[start:end+1] if start != -1 and end != -1 else raw
        data = json.loads(candidate)
        topics = data.get("topics", [])
        links = []
        for t in topics[:num]:
            title = t.get("title") or t.get("query") or "Topic"
            query = t.get("query") or t.get("title") or ""
            if not query:
                continue
            url = f"https://www.youtube.com/results?search_query={requests.utils.quote(query)}"
            links.append({"title": title, "query": query, "url": url})
        if not links:
            raise ValueError("No topics parsed")
        return {"links": links}
    except Exception as e:
        logger.error(f"Links JSON parse failed: {e}; raw=\n{raw}")
        raise HTTPException(status_code=502, detail="Failed to generate links JSON")


