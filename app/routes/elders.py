from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime

from app.db import supabase, elders_table
from app.models import ElderCreate, ElderResponse
from app.routes.auth import get_current_user

router = APIRouter(prefix="/elders", tags=["elders"])


# ✅ Create a new elder profile
@router.post("/", response_model=ElderResponse)
def create_elder(elder: ElderCreate, user=Depends(get_current_user)):
    elder_dict = elder.dict()
    elder_dict["user_id"] = str(user["id"])

    # Ensure relationship is included
    if not elder_dict.get("relationship"):
        raise HTTPException(status_code=400, detail="Relationship is required")

    elder_dict["last_updated"] = datetime.utcnow().isoformat()

    result = supabase.table(elders_table).insert(elder_dict).execute()
    elder_dict["id"] = result.data[0]["id"]
    return elder_dict


# ✅ Get all elders for the current user
@router.get("/", response_model=list[ElderResponse])
def get_elders(user=Depends(get_current_user)):
    result = supabase.table(elders_table).select("*").eq("user_id", str(user["id"])).execute()
    elders = []
    for e in result.data:
        elders.append({
            "id": str(e["id"]),
            "relationship": e.get("relationship", "Unknown"),
            "name": e["name"],
            "age": e["age"],
            "email": e["email"],
            "phone": e["phone"],
            "address": e.get("address"),
            "notes": e.get("notes"),
            "lastUpdated": e.get("last_updated", "")
        })
    return elders


# ✅ Update an elder profile
@router.put("/{elder_id}", response_model=ElderResponse)
def update_elder(elder_id: str, elder: ElderCreate, user=Depends(get_current_user)):
    update_data = elder.dict()

    # Validate relationship field
    if not update_data.get("relationship"):
        raise HTTPException(status_code=400, detail="Relationship is required")

    update_data["last_updated"] = datetime.utcnow().isoformat()

    # Update in database
    result = supabase.table(elders_table).update(update_data).eq("id", elder_id).eq("user_id", str(user["id"])).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Elder not found")

    updated_elder = result.data[0]
    updated_elder["id"] = str(updated_elder["id"])
    updated_elder["relationship"] = updated_elder.get("relationship", "Unknown")
    updated_elder["lastUpdated"] = updated_elder.get("last_updated", "")

    return updated_elder


# ✅ Delete an elder profile
@router.delete("/{elder_id}")
def delete_elder(elder_id: str, user=Depends(get_current_user)):
    result = supabase.table(elders_table).delete().eq("id", elder_id).eq("user_id", str(user["id"])).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Elder not found")

    return {"message": "Elder deleted successfully"}
