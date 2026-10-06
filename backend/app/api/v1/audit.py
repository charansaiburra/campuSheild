from fastapi import APIRouter, Depends, Query
from db.database import SessionLocal
from db.models import AuditLog, User, timestamp_iso_utc
from backend.app.api.v1.auth import get_current_admin

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


@router.get("")
def list_audit_logs(limit: int = Query(100, ge=1, le=500), user: User = Depends(get_current_admin)):
    db = SessionLocal()
    try:
        entries = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
        return [{
            "id": item.id,
            "actor_user_id": item.actor_user_id,
            "action": item.action,
            "resource_type": item.resource_type,
            "resource_id": item.resource_id,
            "details": item.details,
            "created_at": timestamp_iso_utc(item.created_at),
        } for item in entries]
    finally:
        db.close()
