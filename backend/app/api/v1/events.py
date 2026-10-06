import os
from pathlib import Path
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import FileResponse
from typing import Optional
from db.database import SessionLocal
from db.models import SecurityEvent

router = APIRouter(prefix="/events", tags=["Security Events"])

@router.get("/{event_id}/snapshot")
def get_event_snapshot(event_id: str):
    db = SessionLocal()
    try:
        event = db.query(SecurityEvent).filter(SecurityEvent.id == event_id).first()
        if not event:
            raise HTTPException(status_code=404, detail="Security event not found")
        if not event.snapshot_path:
            raise HTTPException(status_code=404, detail="This event has no saved snapshot")
        root = Path(os.path.abspath(os.path.join("data", "snapshots")))
        path = Path(os.path.abspath(event.snapshot_path))
        try:
            path.relative_to(root)
        except ValueError:
            raise HTTPException(status_code=404, detail="Snapshot not found")
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Snapshot not found")
        return FileResponse(path, media_type="image/jpeg")
    finally:
        db.close()

@router.get("")
def list_events(
    event_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    camera_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200)
):
    db = SessionLocal()
    try:
        query = db.query(SecurityEvent)
        if event_type: query = query.filter(SecurityEvent.event_type == event_type)
        if severity: query = query.filter(SecurityEvent.severity == severity)
        if camera_id: query = query.filter(SecurityEvent.camera_id == camera_id)
        if status: query = query.filter(SecurityEvent.status == status)

        events = query.order_by(SecurityEvent.timestamp.desc()).limit(limit).all()
        return [e.to_dict() for e in events]
    finally:
        db.close()
