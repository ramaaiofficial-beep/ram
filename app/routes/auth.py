from fastapi import APIRouter, HTTPException, Depends, status, Body
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr
from typing import Optional

from app.db import supabase, users_table
from app.models import UserCreate, UserLogin, UserProfileResponse
from app.security import hash_password, verify_password, create_access_token, decode_token
import os

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# Partial update model: all fields optional for patch
class UserProfileUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None

# Signup route (also trigger Supabase email confirmation)
@router.post("/signup", status_code=201)
def signup(user: UserCreate):
    # Check if email already exists in local table
    existing_user = supabase.table(users_table).select("id").eq("email", user.email).execute()
    if existing_user.data:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Trigger Supabase Auth sign up to send confirmation mail
    try:
        redirect_url = os.getenv("FRONTEND_URL", "https://www.ramaai.in/")
        supabase.auth.sign_up({
            "email": user.email,
            "password": user.password,
            "options": {"email_redirect_to": redirect_url},
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send confirmation email: {e}")

    # Also keep local users row for the app's custom auth
    hashed = hash_password(user.password)
    supabase.table(users_table).insert({
        "username": user.username,
        "phone": user.phone,
        "email": user.email,
        "password": hashed,
    }).execute()

    return {"message": "Signup submitted. Check your email to confirm your account."}

# Login route
@router.post("/login")
def login(user: UserLogin):
    # Enforce Supabase email confirmation by attempting Supabase Auth sign-in first
    try:
        # This will fail with an error if the email is not confirmed (when confirm email is enabled)
        supabase.auth.sign_in_with_password({
            "email": user.email,
            "password": user.password,
        })
    except Exception as e:
        # Block login until email is confirmed
        msg = str(e)
        raise HTTPException(status_code=403, detail="Email not confirmed. Please confirm your email to continue.")

    # Query user by email
    result = supabase.table(users_table).select("*").eq("email", user.email).execute()
    
    if not result.data or len(result.data) == 0:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    db_user = result.data[0]
    if not verify_password(user.password, db_user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_access_token({
        "user_id": str(db_user["id"]),
        "email": db_user["email"]
    })

    return {"access_token": token, "token_type": "bearer"}

# Dependency to get current user from token
async def get_current_user(token: str = Depends(oauth2_scheme)):
    print(f"\n[Auth] Token received: {token[:20]}...")
    payload = decode_token(token)
    
    if not payload or "user_id" not in payload:
        print(f"[Auth] Invalid token payload: {payload}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    
    print(f"[Auth] User ID from token: {payload['user_id']}")
    print(f"[Auth] Looking up user in database...")
    
    # Query user by ID
    result = supabase.table(users_table).select("*").eq("id", payload["user_id"]).execute()
    
    if not result.data or len(result.data) == 0:
        print(f"[Auth] User not found in database for ID: {payload['user_id']}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    
    print(f"[Auth] User found: {result.data[0].get('email', 'N/A')}")
    return result.data[0]

# Get current logged in user profile
@router.get("/me", response_model=UserProfileResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    return {
        "username": current_user["username"],
        "email": current_user["email"],
        "phone": current_user["phone"]
    }

# Update current logged in user profile (partial update)
@router.patch("/update", response_model=UserProfileResponse)
async def update_profile(
    updated_data: UserProfileUpdate = Body(...),
    current_user: dict = Depends(get_current_user)
):
    update_fields = updated_data.dict(exclude_unset=True)
    if not update_fields:
        raise HTTPException(status_code=400, detail="No update data provided")

    # Check if email is being updated and is unique
    if "email" in update_fields:
        existing_user = supabase.table(users_table).select("id").eq("email", update_fields["email"]).execute()
        if existing_user.data and existing_user.data[0]["id"] != current_user["id"]:
            raise HTTPException(status_code=400, detail="Email already registered")

    # Perform the update
    supabase.table(users_table).update(update_fields).eq("id", current_user["id"]).execute()

    # Fetch updated user from DB
    result = supabase.table(users_table).select("*").eq("id", current_user["id"]).execute()
    updated_user = result.data[0]

    return {
        "username": updated_user["username"],
        "email": updated_user["email"],
        "phone": updated_user["phone"]
    }
