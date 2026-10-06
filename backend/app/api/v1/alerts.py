from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import Literal, Optional
from services.alert_service import AlertService
from db.models import User
from backend.app.api.v1.auth import get_current_user

router = APIRouter(prefix="/alerts", tags=["Alerts"])
alert_service = AlertService()

class AlertStatusUpdateSchema(BaseModel):
    status: Literal["NEW", "ACKNOWLEDGED", "RESOLVED", "DISMISSED"]

@router.get("")
def list_alerts(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(50, le=200)
):
    return alert_service.get_alerts(status=status, severity=severity, limit=limit)

@router.patch("/{alert_id}")
def update_alert_status(alert_id: str, req: AlertStatusUpdateSchema, user: User = Depends(get_current_user)):
    res = alert_service.update_alert_status(alert_id, req.status, user.id)
    if not res:
        raise HTTPException(status_code=400, detail="Failed to update alert status")
    return res
