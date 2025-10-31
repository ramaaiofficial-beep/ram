# app/routes/younger.py

from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime

from app.db import supabase, younger_table
from app.models import YoungerCreate, YoungerResponse
from app.routes.auth import get_current_user

router = APIRouter(prefix="/youngers", tags=["youngers"])


# ✅ Create a new younger profile
@router.post("/", response_model=YoungerResponse)
def create_younger(younger: YoungerCreate, user=Depends(get_current_user)):
    younger_dict = younger.dict()
    younger_dict["user_id"] = str(user["id"])

    # Ensure relationship is included
    if not younger_dict.get("relationship"):
        raise HTTPException(status_code=400, detail="Relationship is required")

    younger_dict["last_updated"] = datetime.utcnow().isoformat()

    result = supabase.table(younger_table).insert(younger_dict).execute()
    inserted = result.data[0]
    # Normalize response keys for frontend
    response_obj = {
        "id": str(inserted["id"]),
        "relationship": inserted.get("relationship", "Unknown"),
        "name": inserted["name"],
        "age": inserted["age"],
        "email": inserted["email"],
        "phone": inserted["phone"],
        "address": inserted.get("address"),
        "notes": inserted.get("notes"),
        "lastUpdated": inserted.get("last_updated", ""),
    }
    return response_obj


# ✅ Get all youngers for the current user
@router.get("/", response_model=list[YoungerResponse])
def get_youngers(user=Depends(get_current_user)):
    result = supabase.table(younger_table).select("*").eq("user_id", str(user["id"])).execute()
    youngers = []
    for y in result.data:
        youngers.append({
            "id": str(y["id"]),
            "relationship": y.get("relationship", "Unknown"),
            "name": y["name"],
            "age": y["age"],
            "email": y["email"],
            "phone": y["phone"],
            "address": y.get("address"),
            "notes": y.get("notes"),
            "lastUpdated": y.get("last_updated", "")
        })
    return youngers


# ✅ Update a younger profile
@router.put("/{younger_id}", response_model=YoungerResponse)
def update_younger(younger_id: str, younger: YoungerCreate, user=Depends(get_current_user)):
    update_data = younger.dict()

    # Validate relationship field
    if not update_data.get("relationship"):
        raise HTTPException(status_code=400, detail="Relationship is required")

    update_data["last_updated"] = datetime.utcnow().isoformat()

    # Update in database
    result = supabase.table(younger_table).update(update_data).eq("id", younger_id).eq("user_id", str(user["id"])).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Younger not found")

    updated = result.data[0]
    # Normalize keys for frontend
    response_obj = {
        "id": str(updated["id"]),
        "relationship": updated.get("relationship", "Unknown"),
        "name": updated["name"],
        "age": updated["age"],
        "email": updated["email"],
        "phone": updated["phone"],
        "address": updated.get("address"),
        "notes": updated.get("notes"),
        "lastUpdated": updated.get("last_updated", ""),
    }

    return response_obj


# ✅ Delete a younger profile
@router.delete("/{younger_id}")
def delete_younger(younger_id: str, user=Depends(get_current_user)):
    result = supabase.table(younger_table).delete().eq("id", younger_id).eq("user_id", str(user["id"])).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Younger not found")

    return {"message": "Younger deleted successfully"}
