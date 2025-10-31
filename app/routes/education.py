from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Depends
from fastapi.responses import JSONResponse, FileResponse
from app.routes.auth import get_current_user
from app.db import supabase, elders_table, education_files_table, education_messages_table
import PyPDF2
import io
import requests
import logging
import os
import base64

router = APIRouter(prefix="/education", tags=["education"])

# ----------------- Logging -----------------
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ----------------- File storage -----------------
UPLOAD_DIR = "uploads"
SONG_DIR = os.path.join(UPLOAD_DIR, "songs")

os.makedirs(SONG_DIR, exist_ok=True)

file_store = {
    "medical": {},  # PDF medical notes (text)
    "stories": {},  # PDF stories (text)
    "songs": {}     # MP3 metadata (just filename → path)
}

# ----------------- Gemini API setup -----------------
GEMINI_API_KEY = "AIzaSyCTlQNa7p7sN6VvBaIXK-IOqoBPa7sduro"
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
HEADERS = {
    "Content-Type": "application/json",
    "X-Goog-Api-Key": GEMINI_API_KEY
}

# ----------------- Helpers -----------------
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


def call_gemini_api(prompt: str) -> str:
    try:
        response = requests.post(
            GEMINI_ENDPOINT,
            headers=HEADERS,
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=20
        )
        response.raise_for_status()
        data = response.json()
        return (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "Gemini returned no answer.")
        )
    except requests.RequestException as e:
        logger.error(f"Gemini API request failed: {e}")
        raise HTTPException(status_code=500, detail="Gemini API request failed.")

def normalize_name(name: str) -> str:
    return name.lower().replace(".mp3", "").strip()

def call_gemini_with_image(image_bytes: bytes, mime_type: str, instruction: str) -> str:
    try:
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": instruction},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": b64,
                            }
                        },
                    ]
                }
            ]
        }
        response = requests.post(
            GEMINI_ENDPOINT,
            headers=HEADERS,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "Gemini returned no answer from image.")
        )
    except requests.RequestException as e:
        logger.error(f"Gemini Vision request failed: {e}")
        raise HTTPException(status_code=500, detail="Gemini Vision request failed.")

# ----------------- Upload Endpoint -----------------
@router.post("/upload/{category}")
async def upload_file(
    category: str,
    file: UploadFile = File(...),
    elder_id: str = Query(..., description="Elder ID that this upload belongs to"),
    user=Depends(get_current_user)
):
    if category not in file_store:
        raise HTTPException(status_code=400, detail="Invalid category: medical, stories, songs.")

    # Validate file type
    if category in ["medical", "stories"]:
        allowed_types = {"application/pdf", "image/jpeg", "image/png", "image/webp"}
        if file.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail="Only PDF or image (jpg/png/webp) allowed for this category.")
    if category == "songs" and not file.filename.lower().endswith(".mp3"):
        raise HTTPException(status_code=400, detail="Only MP3 files allowed for songs.")

    file_bytes = await file.read()
    user_id = str(user["id"])

    # Validate elder belongs to user
    try:
        er = supabase.table(elders_table).select("id").eq("id", elder_id).eq("user_id", user_id).limit(1).execute()  # type: ignore
        if not er.data:
            raise HTTPException(status_code=404, detail="Elder not found for this user")
    except Exception:
        raise HTTPException(status_code=404, detail="Elder not found for this user")
    
    # Create user+elder-specific key
    user_key = f"{user_id}:{elder_id}:{file.filename}"

    if category in ["medical", "stories"]:
        # PDF → extract text, Image → use Gemini Vision to OCR/summarize
        if file.content_type == "application/pdf":
            text = extract_pdf_text(file_bytes, file.filename)
        else:
            instruction = (
                "Extract readable text and key points from this document image. "
                "Return clean, well-structured text suitable for Q&A."
            )
            text = call_gemini_with_image(file_bytes, file.content_type, instruction)
        file_store[category][user_key] = text

        # Persist metadata in DB
        try:
            supabase.table(education_files_table).insert({
                "user_id": user_id,
                "elder_id": elder_id,
                "filename": file.filename,
                "category": category,
                "mime_type": file.content_type,
                "storage_path": None,
                "text_excerpt": text[:1000] if text else None,
            }).execute()
        except Exception as e:
            logger.warning(f"Could not persist education file metadata: {e}")
    else:
        # Save song to disk with user+elder-specific folder
        user_song_dir = os.path.join(SONG_DIR, user_id, elder_id)
        os.makedirs(user_song_dir, exist_ok=True)
        save_path = os.path.join(user_song_dir, file.filename)
        with open(save_path, "wb") as f:
            f.write(file_bytes)
        file_store["songs"][user_key] = save_path

        # Persist song metadata in DB
        try:
            supabase.table(education_files_table).insert({
                "user_id": user_id,
                "elder_id": elder_id,
                "filename": file.filename,
                "category": category,
                "mime_type": "audio/mpeg",
                "storage_path": save_path,
                "text_excerpt": None,
            }).execute()
        except Exception as e:
            logger.warning(f"Could not persist song metadata: {e}")

    logger.info(f"✅ Uploaded '{file.filename}' to {category} for user {user_id}")

    if category == "songs":
        message = f"✅ Song '{file.filename}' uploaded successfully."
    elif category == "stories":
        message = f"✅ Story '{file.filename}' uploaded. You can now ask me about it!"
    else:
        message = f"✅ File '{file.filename}' uploaded to {category}."

    return JSONResponse(content={"message": message})


# ----------------- Fetch Story -----------------
@router.get("/fetch/story")
async def fetch_story(filename: str, elder_id: str = Query(...), user=Depends(get_current_user)):
    user_id = str(user["id"])
    user_key = f"{user_id}:{elder_id}:{filename}"
    
    if user_key not in file_store["stories"]:
        raise HTTPException(status_code=404, detail="Story not found.")
    return {"story": file_store["stories"][user_key]}


# ----------------- Fetch Song -----------------
@router.get("/fetch/song")
async def fetch_song(filename: str, elder_id: str = Query(...), user=Depends(get_current_user)):
    user_id = str(user["id"])
    user_key = f"{user_id}:{elder_id}:{filename}"
    
    if user_key not in file_store["songs"]:
        raise HTTPException(status_code=404, detail="Song not found.")
    song_path = file_store["songs"][user_key]
    return FileResponse(song_path, media_type="audio/mpeg", filename=filename)


# ----------------- Ask Question -----------------
@router.get("/ask")
async def ask_question(
    question: str = Query(..., description="The user's question."),
    filename: str = Query(None, description="Optional PDF filename for context"),
    elder_id: str = Query(..., description="Elder ID for scoping context"),
    user=Depends(get_current_user)
):
    """
    Handles Q&A:
      - If user asks to play a song → return its URL.
      - If filename is provided → answer using that file.
      - Otherwise → merge all uploaded docs or fall back to Gemini.
    """

    user_id = str(user["id"])
    q_lower = question.lower()

    # Persist the user message immediately so it is not lost on refresh
    try:
        supabase.table(education_messages_table).insert({
            "user_id": user_id,
            "elder_id": elder_id,
            "role": "user",
            "content": question,
        }).execute()
    except Exception as e:
        logger.warning(f"Could not persist user message: {e}")

    # ---------- Song playback detection ----------
    # Only check user's own songs
    user_songs = {k: v for k, v in file_store["songs"].items() if k.startswith(f"{user_id}:{elder_id}:")}
    if "play" in q_lower and user_songs:
        for song_key in user_songs.keys():
            song_name = song_key.split(":", 1)[1]
            if normalize_name(song_name) in q_lower:
                song_url = f"/education/fetch/song?filename={song_name}&elder_id={elder_id}"
                answer_text = f"🎵 Playing '{song_name}'..."
                # Persist assistant reply for song path
                try:
                    supabase.table(education_messages_table).insert({
                        "user_id": user_id,
                        "elder_id": elder_id,
                        "role": "assistant",
                        "content": answer_text,
                    }).execute()
                except Exception as e:
                    logger.warning(f"Could not persist assistant message (song): {e}")
                return {"answer": answer_text, "song_url": song_url}

        song_names = [k.split(":", 1)[1] for k in user_songs.keys()]
        song_list = ", ".join(song_names)
        answer_text = f"🎶 I found these songs: {song_list}. Please specify which one to play."
        try:
            supabase.table(education_messages_table).insert({
                "user_id": user_id,
                "elder_id": elder_id,
                "role": "assistant",
                "content": answer_text,
            }).execute()
        except Exception as e:
            logger.warning(f"Could not persist assistant message (song-list): {e}")
        return {"answer": answer_text}

    # ---------- Document Q&A ----------
    merged_text = ""

    if filename:
        found = False
        user_key = f"{user_id}:{elder_id}:{filename}"
        for cat in ["medical", "stories"]:
            if user_key in file_store[cat]:
                merged_text = file_store[cat][user_key]
                found = True
                break
        if not found:
            merged_text = ""
    else:
        # Only include user's own files
        for cat in ["medical", "stories"]:
            for fkey, text in file_store[cat].items():
                if fkey.startswith(f"{user_id}:{elder_id}:"):
                    fname = fkey.split(":", 1)[1]
                    merged_text += f"[{cat.upper()} - {fname}]\n{text[:3000]}\n\n"

    if user_songs:
        merged_text += "\nUploaded Songs:\n"
        for song_key in user_songs.keys():
            song_name = song_key.split(":", 1)[1]
            merged_text += f"- {song_name}\n"

    context_info = merged_text.strip() or "No uploaded documents or songs. Use general knowledge."

    prompt = f"""
You are a helpful assistant that can answer questions using uploaded documents or general knowledge.

Context:
\"\"\"{context_info[:16000]}\"\"\" 

Question:
{question}

Answer in a clear and helpful way:
"""

    answer = call_gemini_api(prompt)
    # Persist assistant answer (user already saved above)
    try:
        supabase.table(education_messages_table).insert({
            "user_id": user_id,
            "elder_id": elder_id,
            "role": "assistant",
            "content": answer,
        }).execute()
    except Exception as e:
        logger.warning(f"Could not persist assistant message: {e}")

    return {"answer": answer}


# ----------------- List Files -----------------
@router.get("/files")
async def list_files(elder_id: str = Query(...), user=Depends(get_current_user)):
    user_id = str(user["id"])
    try:
        res = supabase.table(education_files_table).select("id, filename, category, mime_type, created_at").eq("user_id", user_id).eq("elder_id", elder_id).order("created_at", desc=True).execute()
        return res.data
    except Exception as e:
        logger.error(f"Failed to list education files: {e}")
        raise HTTPException(status_code=500, detail="Failed to list files")


# ----------------- Delete File -----------------
@router.delete("/file")
async def delete_file(
    elder_id: str = Query(...),
    filename: str = Query(...),
    category: str = Query(..., description="medical|stories|songs"),
    user=Depends(get_current_user)
):
    user_id = str(user["id"])
    if category not in ["medical", "stories", "songs"]:
        raise HTTPException(status_code=400, detail="Invalid category")

    # Remove in-memory or disk copy
    key_prefix = f"{user_id}:{elder_id}:{filename}"
    if category in ["medical", "stories"]:
        try:
            file_store[category].pop(key_prefix, None)
        except Exception:
            pass
    else:
        # songs: remove file on disk
        path = file_store["songs"].pop(key_prefix, None)
        if path:
            try:
                import os
                if os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                logger.warning(f"Could not remove song file: {e}")

    # Remove metadata row from DB
    try:
        (
            supabase
            .table(education_files_table)
            .delete()
            .eq("user_id", user_id)
            .eq("elder_id", elder_id)
            .eq("filename", filename)
            .eq("category", category)
            .execute()
        )
    except Exception as e:
        logger.warning(f"Could not delete metadata row: {e}")

    return {"message": "Deleted"}


# ----------------- Generate Quiz -----------------
@router.get("/quiz")
def generate_quiz(
    elder_id: str = Query(...),
    filename: str = Query(...),
    num: int = Query(10, ge=1, le=20),
    user=Depends(get_current_user)
):
    user_id = str(user["id"])
    key = f"{user_id}:{elder_id}:{filename}"
    # Build context from specific file
    context = ""
    for cat in ["medical", "stories"]:
        if key in file_store[cat]:
            context = file_store[cat][key]
            break
    if not context:
        raise HTTPException(status_code=404, detail="No context found for this file")

    instruction = f"""
From the following material, create {num} multiple-choice questions for learning.
Return STRICT JSON only with this schema (no prose):
{{"questions":[{{"question":"...","options":["A","B","C","D"],"answerIndex":0}}]}}
Each question must have exactly 4 distinct options and a correct answerIndex 0-3.

Material:\n\n{context[:12000]}
"""

    raw = call_gemini_api(instruction)
    import json
    try:
        start = raw.find('{'); end = raw.rfind('}')
        candidate = raw[start:end+1] if start != -1 and end != -1 else raw
        data = json.loads(candidate)
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
        logger.error(f"Education quiz JSON parse failed: {e}; raw=\n{raw}")
        raise HTTPException(status_code=502, detail="Failed to generate quiz JSON")


# ----------------- List Messages -----------------
@router.get("/messages")
async def list_messages(
    elder_id: str = Query(...),
    limit: int = Query(50, ge=1, le=200),
    user=Depends(get_current_user)
):
    user_id = str(user["id"])
    try:
        res = (
            supabase
            .table(education_messages_table)
            .select("id, role, content, created_at")
            .eq("user_id", user_id)
            .eq("elder_id", elder_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        # return in chronological order
        data = list(reversed(res.data))
        return data
    except Exception as e:
        logger.error(f"Failed to list education messages: {e}")
        raise HTTPException(status_code=500, detail="Failed to list messages")
