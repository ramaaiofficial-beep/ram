from supabase import create_client
from dotenv import load_dotenv
import os
from pathlib import Path

# Get the backend directory (parent of app)
BASE_DIR = Path(__file__).resolve().parent.parent
# Load .env file from the backend directory
load_dotenv(dotenv_path=BASE_DIR / ".env")

# Supabase credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("SUPABASE_URL and SUPABASE_KEY must be set in environment variables")

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Table names (kept for compatibility with existing code)
users_table = "users"
elders_table = "elders"
younger_table = "younger"
chat_history_table = "chat_history"
reminders_table = "reminders"
education_files_table = "education_files"
education_messages_table = "education_messages"
