from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.routes import auth, elders, younger, chat, education, medications  # ✅ added medications router
from app.routes import generalknowledge, educationy
from app.db import supabase  # import the Supabase client
from app.routes import quiz
from app.routes import song  # ✅ import
import os


app = FastAPI(title="RAMA AI Backend")

# Log all incoming requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    print(f"\n[REQUEST] {request.method} {request.url.path}")
    response = await call_next(request)
    print(f"[RESPONSE] Status: {response.status_code}\n")
    return response

# CORS Configuration
# Allow all origins but without credentials for wildcard compatibility
# Get allowed origins from environment or use wildcard
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # Can be ["*"] or specific URLs
    allow_credentials=True if "*" not in allowed_origins else False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(elders.router)
app.include_router(younger.router)
app.include_router(chat.router)
app.include_router(education.router)
app.include_router(song.router)  # ✅ include
app.include_router(medications.router)  # ✅ include medications router (no prefix - endpoints already have /medications/)
app.include_router(quiz.router, prefix="/quiz", tags=["Quiz"])
app.include_router(generalknowledge.router)
app.include_router(educationy.router)

@app.get("/")
def root():
    return {"message": "RAMA AI backend is running"}

@app.get("/check-db")
def check_db():
    try:
        # Test Supabase connection by querying a simple table
        supabase.table("users").select("id").limit(1).execute()
        return {"message": "Supabase connection successful"}
    except Exception as e:
        return {"message": "Supabase connection failed", "error": str(e)}
