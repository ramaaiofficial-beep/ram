from fastapi import APIRouter, HTTPException, Path, Depends
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from twilio.rest import Client
from dotenv import load_dotenv
from typing import List, Optional
import os

from app.db import supabase, reminders_table
from app.routes.auth import get_current_user

# ------------------ Load Environment Variables ------------------
load_dotenv()

# ------------------ Router Setup ------------------
router = APIRouter(prefix="/medications", tags=["medications"])

# ------------------ Twilio Setup ------------------
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# Twilio setup is optional for medication reminders
# Only initialize if all credentials are provided
if all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER]):
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
else:
    twilio_client = None
    print("WARNING: Twilio credentials not set. Medication reminders will not be available.")

# ------------------ Scheduler Setup ------------------
scheduler = BackgroundScheduler()
scheduler.start()

# ------------------ Pydantic Models ------------------
class SMSRequest(BaseModel):
    patient_name: str = Field(..., example="John Doe")
    medication_name: str = Field(..., example="Aspirin")
    dosage: str = Field(..., example="100mg")
    send_time: str = Field(..., example="14:30")  # Format: "HH:MM" 24-hour
    phone_number: str = Field(..., example="+1234567890")
    elder_id: Optional[str] = Field(None, example="123e4567-e89b-12d3-a456-426614174000")
    frequency: Optional[str] = Field(None, example="1-0-1")

class ReminderOut(BaseModel):
    id: str
    patient_name: str
    medication_name: str
    dosage: str
    send_time: datetime
    phone_number: str
    created_at: datetime
    elder_id: Optional[str] = None
    frequency: Optional[str] = None

# ------------------ SMS Task Function ------------------
def send_sms_task(patient_name: str, medication_name: str, dosage: str, phone_number: str):
    if not twilio_client:
        print(f"SMS reminder for {patient_name} skipped (Twilio not configured)")
        return
    try:
        twilio_client.messages.create(
            body=f"Hello {patient_name}, remember to take {medication_name} ({dosage}).",
            from_=TWILIO_PHONE_NUMBER,
            to=phone_number
        )
        print(f"SMS sent to {phone_number}")
    except Exception as e:
        print(f"Failed to send SMS to {phone_number}: {e}")

# ------------------ API Endpoints ------------------

@router.get("/test")
async def test_medications():
    try:
        result = supabase.table(reminders_table).select("*").order("created_at", desc=True).limit(5).execute()
        users_result = supabase.table("users").select("id, email, username").order("created_at", desc=True).execute()
        return {
            "success": True,
            "reminder_count": len(result.data),
            "reminders": result.data,
            "users": users_result.data
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/test-my-reminders")
async def test_my_reminders(user=Depends(get_current_user)):
    try:
        result = supabase.table(reminders_table).select("*").eq("user_id", str(user["id"])).execute()
        return {
            "success": True,
            "user_id": str(user["id"]),
            "user_email": user.get("email", "N/A"),
            "my_reminder_count": len(result.data),
            "my_reminders": result.data
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.post("/test-insert")
async def test_insert():
    try:
        test_data = {
            "patient_name": "Test Patient",
            "medication_name": "Test Medication",
            "dosage": "100mg",
            "send_time": "2024-12-31T12:00:00Z",
            "phone_number": "+1234567890",
            "created_at": datetime.utcnow().isoformat(),
        }
        result = supabase.table(reminders_table).insert(test_data).execute()
        return {"success": True, "message": "Test reminder inserted", "data": result.data}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.post("/schedule-reminder")
async def schedule_sms(request: SMSRequest, user=Depends(get_current_user)):
    print("\n" + "=" * 80)
    print("RECEIVED REMINDER REQUEST")
    print(f"Patient: {request.patient_name}")
    print(f"Medication: {request.medication_name}")
    print(f"Time: {request.send_time}")
    print(f"User ID: {str(user['id'])}")
    print(f"User Email: {user.get('email', 'N/A')}")
    print("=" * 80 + "\n")
    now = datetime.now()

    # Parse and validate time string "HH:MM"
    try:
        hour, minute = map(int, request.send_time.strip().split(":"))
        if not (0 <= hour < 24 and 0 <= minute < 60):
            raise ValueError("Hour or minute out of range")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid time format. Use 'HH:MM' in 24-hour format.")

    # Compute next datetime for SMS sending
    send_datetime = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if send_datetime < now:
        send_datetime += timedelta(days=1)

    # Create a unique job id
    job_id = f"sms_{request.patient_name}_{int(send_datetime.timestamp())}"

    # Remove existing job if any
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    # Schedule SMS job
    scheduler.add_job(
        func=send_sms_task,
        trigger='date',
        run_date=send_datetime,
        args=[
            request.patient_name,
            request.medication_name,
            request.dosage,
            request.phone_number,
        ],
        id=job_id,
        replace_existing=True,
    )

    # Insert minimal required fields first
    reminder_min = {
        "patient_name": request.patient_name,
        "medication_name": request.medication_name,
        "dosage": request.dosage,
        "send_time": send_datetime.isoformat(),
        "phone_number": request.phone_number,
        "created_at": datetime.utcnow().isoformat(),
        "user_id": str(user["id"]),
    }

    # Prefer inserting optional fields directly when present
    optional_update = {}
    if request.frequency:
        reminder_min["frequency"] = request.frequency
    if request.elder_id:
        reminder_min["elder_id"] = request.elder_id

    try:
        result = supabase.table(reminders_table).insert(reminder_min).execute()
        print("Reminder saved successfully!")
        print(f"Inserted ID: {result.data[0]['id']}")
        inserted = result.data[0]
    except Exception as e:
        print(f"ERROR saving with user_id: {e}")
        try:
            fallback_min = dict(reminder_min)
            fallback_min.pop("user_id", None)
            result = supabase.table(reminders_table).insert(fallback_min).execute()
            print("Reminder saved without user_id")
            print(f"Inserted ID: {result.data[0]['id']}")
            inserted = result.data[0]
        except Exception as e2:
            print("ERROR: Failed to save reminder entirely:", e2)
            raise HTTPException(status_code=500, detail=f"Failed to save reminder: {str(e2)}")

    # Best-effort apply optional fields via update (ignore failures)
    if optional_update:
        try:
            supabase.table(reminders_table).update(optional_update).eq("id", inserted["id"]).execute()
            print("✅ Applied optional fields successfully:", optional_update)
        except Exception as opt_e:
            print("❌ ERROR: Failed to apply optional fields:", opt_e)
            print("⚠️ Reminder saved without optional fields. elder_id and/or frequency may be missing.")

    return {
        "message": f"📅 Reminder scheduled for {send_datetime.strftime('%Y-%m-%d %H:%M')}",
        "reminder": {
            "id": inserted["id"],
            "patient_name": request.patient_name,
            "medication_name": request.medication_name,
            "dosage": request.dosage,
            "send_time": send_datetime.isoformat(),
            "phone_number": request.phone_number,
            "frequency": request.frequency,
        }
    }

@router.get("/reminders", response_model=List[ReminderOut])
async def get_reminders(user=Depends(get_current_user), elder_id: Optional[str] = None):
    print("\nFETCHING REMINDERS FOR USER:", str(user['id']))
    if elder_id:
        print(f"Filtering by elder_id: {elder_id}")
    reminders: List[ReminderOut] = []
    try:
        query = supabase.table(reminders_table).select("*").eq("user_id", str(user["id"]))
        if elder_id:
            query = query.eq("elder_id", elder_id)
        result = query.execute()
        print(f"Found {len(result.data)} reminders for user {user['id']}")

        for doc in result.data:
            created_at = doc.get("created_at")
            if created_at:
                try:
                    if isinstance(created_at, str):
                        created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                except Exception:
                    created_at = datetime.utcnow()
            else:
                created_at = datetime.utcnow()

            reminders.append(
                ReminderOut(
                    id=str(doc["id"]),
                    patient_name=doc["patient_name"],
                    medication_name=doc["medication_name"],
                    dosage=doc["dosage"],
                    send_time=datetime.fromisoformat(doc["send_time"].replace("Z", "+00:00")),
                    phone_number=doc["phone_number"],
                    created_at=created_at,
                    elder_id=doc.get("elder_id"),
                    frequency=doc.get("frequency"),
                )
            )
        print(f"Returning {len(reminders)} reminders")
        return reminders
    except Exception as e:
        print("Error in get_reminders:", e)
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/reminders/{reminder_id}")
async def delete_reminder(reminder_id: str = Path(..., description="The ID of the reminder to delete"), user=Depends(get_current_user)):
    print(f"\nDELETE REQUEST - Reminder ID: {reminder_id}, User: {str(user['id'])}")
    try:
        jobs = scheduler.get_jobs()
        for job in jobs:
            if reminder_id in job.id:
                scheduler.remove_job(job.id)
                break

        try:
            result = supabase.table(reminders_table).delete().eq("id", reminder_id).eq("user_id", str(user["id"])).execute()
        except Exception as e:
            print("Note: Deleting reminder without user_id check:", e)
            result = supabase.table(reminders_table).delete().eq("id", reminder_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Reminder not found")
        return {"message": "Reminder deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

