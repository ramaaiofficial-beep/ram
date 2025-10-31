from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List

# ✅ Auth
class UserCreate(BaseModel):
    username: str
    phone: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


# ✅ Profile
class ProfileBase(BaseModel):
    name: str
    age: int
    email: EmailStr
    phone: str
    address: Optional[str]
    notes: Optional[str]


class ProfileCreate(ProfileBase):
    pass


class ProfileUpdate(ProfileBase):
    pass


class Profile(ProfileBase):
    id: str
    lastUpdated: str


# ✅ Chat
class ChatMessage(BaseModel):
    message: str


# ✅ Elder models (updated)
class ElderCreate(BaseModel):
    relationship: str = Field(..., description="Relationship with the elder (e.g., Father, Mother)")
    name: str
    age: int
    email: str
    phone: str
    address: Optional[str] = None
    notes: Optional[str] = None


class ElderResponse(ElderCreate):
    id: str
    lastUpdated: Optional[str] = None


# ✅ Younger models
class YoungerCreate(BaseModel):
    relationship: Optional[str] = None  # make optional
    name: str
    age: int
    email: EmailStr
    phone: str
    address: Optional[str] = None
    notes: Optional[str] = None


class YoungerResponse(YoungerCreate):
    id: str
    lastUpdated: Optional[str] = None


# ✅ Used for /auth/me response
class UserProfileResponse(BaseModel):
    username: str
    email: EmailStr
    phone: str
