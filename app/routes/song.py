from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from supabase import create_client
from urllib.parse import unquote
import time
import requests
import subprocess
import os

router = APIRouter(prefix="/api/songs", tags=["Songs"])

# ---------------------------
# 🔐 Supabase Credentials
# ---------------------------
SUPABASE_URL = "https://mhzvylcapuhrmpkoyjel.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1oenZ5bGNhcHVocm1wa295amVsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTg5MDI1NzMsImV4cCI6MjA3NDQ3ODU3M30.SiIpS6KV-BDBqSIv5rBPlO6MGdA055otspaCo9PHXsE"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
BUCKET_NAME = "songs"

# ---------------------------
# 🧠 Whisper.cpp Configuration
# ---------------------------
WHISPER_BIN = r"D:\whisper.cpp\build\bin\Release\whisper-cli.exe"
WHISPER_MODEL = r"D:\whisper.cpp\ggml-large-v3.bin"
TEMP_DIR = r"D:\whisper_temp"
os.makedirs(TEMP_DIR, exist_ok=True)



# 🧠 Get all uploaded songs
@router.get("/")
def list_songs():
    try:
        files = supabase.storage.from_(BUCKET_NAME).list()
        songs = [
            {
                "name": f["name"],
                "url": supabase.storage.from_(BUCKET_NAME).get_public_url(f["name"]),
            }
            for f in files
        ]
        return {"songs": songs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing songs: {e}")


# 🎵 Upload new song
@router.post("/upload")
async def upload_song(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        timestamp = int(time.time())
        file_name = f"{timestamp}_{file.filename}"

        response = supabase.storage.from_(BUCKET_NAME).upload(file_name, contents)

        if isinstance(response, dict) and response.get("error"):
            raise HTTPException(status_code=500, detail=response["error"]["message"])

        file_url = supabase.storage.from_(BUCKET_NAME).get_public_url(file_name)

        return {
            "message": "✅ Song uploaded successfully!",
            "file_name": file_name,
            "url": file_url,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading song: {e}")


# 🗑️ Delete song
@router.delete("/{song_name}")
def delete_song(song_name: str):
    """
    Deletes a song from Supabase Storage.
    """
    try:
        decoded_name = unquote(song_name)

        # Perform delete
        result = supabase.storage.from_(BUCKET_NAME).remove([decoded_name])

        if isinstance(result, dict) and result.get("error"):
            raise HTTPException(status_code=500, detail=result["error"]["message"])

        return {"message": f"🗑️ '{decoded_name}' deleted successfully!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting song: {e}")


# 🎧 Transcribe song with Whisper.cpp
@router.post("/transcribe/{song_name}")
def transcribe_song(song_name: str):
    try:
        decoded_name = unquote(song_name)
        file_url = supabase.storage.from_(BUCKET_NAME).get_public_url(decoded_name)

        if not file_url:
            raise HTTPException(status_code=404, detail="File not found in Supabase.")

        local_path = os.path.join(TEMP_DIR, decoded_name)
        response = requests.get(file_url)
        with open(local_path, "wb") as f:
            f.write(response.content)

        transcript_path = local_path + ".txt"
        cmd = [WHISPER_BIN, "-m", WHISPER_MODEL, "-f", local_path, "-otxt"]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Whisper error: {result.stderr}")

        if os.path.exists(transcript_path):
            with open(transcript_path, "r", encoding="utf-8") as f:
                transcription = f.read()
        else:
            raise HTTPException(status_code=500, detail="Transcript file not found.")

        return {"song": decoded_name, "transcription": transcription.strip()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error transcribing song: {e}")


# 🎤 Get lyrics (transcription) of a song
@router.get("/{song_name}/lyrics")
def get_lyrics(song_name: str):
    """
    Returns the transcription/lyrics of a song using Whisper.cpp.
    This uses the existing transcribe endpoint to extract lyrics from the audio.
    """
    try:
        decoded_name = unquote(song_name)
        file_url = supabase.storage.from_(BUCKET_NAME).get_public_url(decoded_name)

        if not file_url:
            raise HTTPException(status_code=404, detail="File not found in Supabase.")

        local_path = os.path.join(TEMP_DIR, decoded_name)
        
        # Download the file
        response = requests.get(file_url)
        with open(local_path, "wb") as f:
            f.write(response.content)

        transcript_path = local_path + ".txt"
        
        # Check if transcript already exists
        if os.path.exists(transcript_path):
            with open(transcript_path, "r", encoding="utf-8") as f:
                lyrics = f.read()
        else:
            # Use Whisper to generate transcript
            cmd = [WHISPER_BIN, "-m", WHISPER_MODEL, "-f", local_path, "-otxt"]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                raise HTTPException(status_code=500, detail=f"Whisper error: {result.stderr}")

            if os.path.exists(transcript_path):
                with open(transcript_path, "r", encoding="utf-8") as f:
                    lyrics = f.read()
            else:
                raise HTTPException(status_code=500, detail="Transcript file not found.")

        # Clean up local file
        if os.path.exists(local_path):
            os.remove(local_path)

        return {"song": decoded_name, "lyrics": lyrics.strip()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching lyrics: {str(e)}")