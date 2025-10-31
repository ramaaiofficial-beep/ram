from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.db import supabase, elders_table, younger_table, reminders_table
from app.routes.auth import get_current_user
import requests
import traceback
import os

# ============================================================
# Create the API router
# ============================================================
router = APIRouter(prefix="/chat", tags=["chat"])

# ============================================================
# Define request body schema
# ============================================================
class ChatMessage(BaseModel):
    message: str

# ============================================================
# Gemini API config
# ============================================================
GEMINI_API_KEY = "AIzaSyCTlQNa7p7sN6VvBaIXK-IOqoBPa7sduro"
GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash:generateContent"
)

headers = {
    "Content-Type": "application/json",
    "X-Goog-Api-Key": GEMINI_API_KEY,
}

# ============================================================
# Load Knowledge Base (Fixed Path for backend/data)
# ============================================================
def load_knowledge_file():
    try:
        # Go up two levels from routes → app → backend
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        file_path = os.path.join(base_dir, "data", "rama_ai_knowledge.txt")

        print("Looking for knowledge base at:", file_path)
        print("Current working dir:", os.getcwd())

        if not os.path.exists(file_path):
            print("WARNING: Knowledge base file not found at:", file_path)
            return ""

        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read().strip()

        print(f"SUCCESS: Rama AI Knowledge Base Loaded ({len(text)} characters)")
        return text

    except Exception as e:
        print("ERROR: Error loading knowledge base:", e)
        print(traceback.format_exc())
        return ""

# Load it once at startup
knowledge_text = load_knowledge_file()

# ============================================================
# Clean up AI response to make it more human-like
# ============================================================
def humanize_response(text: str) -> str:
    """Clean up AI response to make it sound more natural and human-like"""
    if not text:
        return text
    
    # Remove common AI phrases and replace with more natural ones
    replacements = {
        "I understand": "I see",
        "I can help you with": "I can tell you about",
        "Based on my knowledge": "From what I know",
        "I'm an AI": "I'm Rama",
        "As an AI": "As Rama",
        "I don't have": "I don't know",
        "I cannot": "I can't",
        "I will": "I'll",
        "I have": "I've",
        "I am": "I'm",
        "You are": "You're",
        "Do not": "Don't",
        "Cannot": "Can't",
        "Will not": "Won't",
        "Should not": "Shouldn't",
        "Would not": "Wouldn't",
        "Could not": "Couldn't",
        "Have not": "Haven't",
        "Has not": "Hasn't",
        "Had not": "Hadn't",
        "Is not": "Isn't",
        "Are not": "Aren't",
        "Was not": "Wasn't",
        "Were not": "Weren't",
    }
    
    # Apply replacements
    for formal, casual in replacements.items():
        text = text.replace(formal, casual)
    
    # Remove excessive punctuation and formatting
    text = text.replace("...", ".")
    text = text.replace("!!", "!")
    text = text.replace("??", "?")
    
    # Remove bullet points and replace with natural flow
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        line = line.strip()
        if line.startswith(('•', '-', '*', '1.', '2.', '3.', '4.', '5.')):
            # Convert bullet points to natural sentences
            line = line.lstrip('•-*123456789. ')
            if line:
                cleaned_lines.append(line + ".")
        elif line:
            cleaned_lines.append(line)
    
    return ' '.join(cleaned_lines).strip()

# ============================================================
# Ask Gemini (with or without context)
# ============================================================
def ask_gemini(prompt: str, use_context: bool = False) -> str:
    if use_context and knowledge_text:
        prompt = f"""
You are Rama, a warm and caring friend who happens to be very knowledgeable. You speak naturally, like a real person would - not like a formal AI assistant.

Below is your knowledge base:
---
{knowledge_text}
---

Now respond to this question as Rama would - naturally, warmly, and conversationally:
"{prompt}"

Important guidelines:
- Write like a human friend, not an AI
- Use natural language and contractions (I'm, you're, don't, etc.)
- Avoid formal AI phrases like "I understand", "I can help you with", "Based on my knowledge"
- Don't use bullet points or numbered lists unless absolutely necessary
- Keep responses conversational and personal
- If you don't know something, say so naturally like "I'm not sure about that" or "That's not something I know much about"
- Use simple, everyday language
- Be warm and empathetic
"""

    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        response = requests.post(GEMINI_ENDPOINT, headers=headers, json=payload)
        if response.status_code == 200:
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        else:
            print("ERROR: Gemini API Error:", response.status_code, response.text)
            return f"Gemini API Error: {response.status_code}"
    except Exception:
        print("ERROR: Gemini API Request Failed")
        print(traceback.format_exc())
        return "Error getting response from Gemini."

# ============================================================
# Chat Endpoint
# ============================================================
@router.post("/")
def chat(msg: ChatMessage, user=Depends(get_current_user)):
    try:
        print("Incoming message:", msg.message)
        print(f"User ID: {user['id']}")

        # Check elder profile - NOW FILTERED BY USER ID
        elder_result = supabase.table(elders_table).select("*").ilike("name", f"%{msg.message}%").eq("user_id", str(user["id"])).execute()
        if elder_result.data and len(elder_result.data) > 0:
            elder = elder_result.data[0]
            profile = {
                "name": elder.get("name"),
                "age": elder.get("age"),
                "email": elder.get("email"),
                "phone": elder.get("phone"),
                "address": elder.get("address", ""),
                "notes": elder.get("notes", ""),
            }
            # Fetch up to 5 upcoming medication reminders for this elder
            reminders_list = []
            try:
                r_result = (
                    supabase
                    .table(reminders_table)
                    .select("id, medication_name, dosage, send_time, phone_number, frequency")
                    .eq("user_id", str(user["id"]))
                    .eq("elder_id", str(elder["id"]))
                    .order("send_time")
                    .limit(5)
                    .execute()
                )
                for r in r_result.data:
                    reminders_list.append({
                        "id": str(r.get("id")),
                        "medication_name": r.get("medication_name"),
                        "dosage": r.get("dosage"),
                        "send_time": r.get("send_time"),
                        "phone_number": r.get("phone_number"),
                        "frequency": r.get("frequency"),
                    })
            except Exception as e:
                print("Warning: could not fetch reminders:", e)

            # Do not prepend a long sentence; frontend will render profile and reminders cards
            reply = ""

            return {
                "reply": reply,
                "profile": profile,
                "reminders": reminders_list,
            }

        # Check younger profile - NOW FILTERED BY USER ID
        younger_result = supabase.table(younger_table).select("*").ilike("name", f"%{msg.message}%").eq("user_id", str(user["id"])).execute()
        if younger_result.data and len(younger_result.data) > 0:
            younger = younger_result.data[0]
            profile = {
                "name": younger.get("name"),
                "age": younger.get("age"),
                "email": younger.get("email"),
                "phone": younger.get("phone"),
                "address": younger.get("address", ""),
                "notes": younger.get("notes", ""),
            }
            return {
                "reply": f"Here is the younger profile of {profile['name']}.",
                "profile": profile,
            }

        # Use Gemini with knowledge base as context
        print("Using Gemini with knowledge base context...")
        gemini_reply = ask_gemini(msg.message, use_context=True)
        # Humanize the response to make it sound more natural
        humanized_reply = humanize_response(gemini_reply)
        return {"reply": humanized_reply}

    except Exception:
        print("ERROR: Error occurred in /chat/")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal Server Error")