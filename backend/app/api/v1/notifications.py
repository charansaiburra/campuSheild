from fastapi import APIRouter, HTTPException, Query
from services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])
service = NotificationService()


@router.get("")
def list_notifications(unread_only: bool = Query(False), limit: int = Query(100, ge=1, le=200)):
    return service.list(unread_only=unread_only, limit=limit)


@router.get("/unread-count")
def unread_count():
    return {"count": service.unread_count()}


@router.patch("/read-all")
def mark_all_read():
    return {"updated": service.mark_all_read()}


@router.patch("/{notification_id}/read")
def mark_read(notification_id: str):
    result = service.mark_read(notification_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return result
