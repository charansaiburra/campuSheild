from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any
from db.database import SessionLocal
from db.models import SystemSetting, User, AuditLog
from datetime import datetime, timezone
from backend.app.api.v1.auth import get_current_admin

router = APIRouter(prefix="/settings", tags=["System Settings"])

class SettingUpdateSchema(BaseModel):
    key: str
    value: str

@router.get("")
def list_settings():
    db = SessionLocal()
    try:
        settings = db.query(SystemSetting).all()
        return [s.to_dict() for s in settings]
    finally:
        db.close()

@router.put("")
def update_setting(req: SettingUpdateSchema, user: User = Depends(get_current_admin)):
    supported = {
        "FACE_VERIFICATION_THRESHOLD": (0.30, 0.99, float),
        "CROWD_THRESHOLD": (1, 10000, int),
        "CROWD_ALERT_COOLDOWN_SECONDS": (0, 86400, float),
        "ZONE_BREACH_COOLDOWN_SECONDS": (0, 86400, float),
    }
    constraints = supported.get(req.key)
    if not constraints:
        raise HTTPException(status_code=400, detail="This setting is not supported by an active backend feature")
    minimum, maximum, value_type = constraints
    try:
        numeric_value = value_type(req.value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"{req.key} must be a valid {value_type.__name__} value")
    if not minimum <= numeric_value <= maximum:
        raise HTTPException(status_code=400, detail=f"{req.key} must be between {minimum} and {maximum}")

    db = SessionLocal()
    try:
        s = db.query(SystemSetting).filter(SystemSetting.key == req.key).first()
        if not s:
            descriptions = {
                "FACE_VERIFICATION_THRESHOLD": "Cosine similarity threshold for face verification",
                "CROWD_THRESHOLD": "Number of people that triggers a crowd event",
                "CROWD_ALERT_COOLDOWN_SECONDS": "Cooldown between duplicate crowd alerts",
                "ZONE_BREACH_COOLDOWN_SECONDS": "Cooldown between duplicate zone violation alerts",
            }
            s = SystemSetting(key=req.key, value=str(numeric_value), description=descriptions[req.key])
            db.add(s)
        else:
            s.value = str(numeric_value)
        db.add(AuditLog(
            actor_user_id=user.id,
            action="SYSTEM_SETTING_UPDATED",
            resource_type="system_setting",
            resource_id=req.key,
            details=f"Updated {req.key}",
            created_at=datetime.now(timezone.utc),
        ))
        db.commit()
        return s.to_dict()
    finally:
        db.close()
