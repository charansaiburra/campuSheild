from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, model_validator
from typing import Optional, Literal
from datetime import datetime, timezone
from db.database import SessionLocal
from db.models import Camera, User, AuditLog
from services.event_service import EventService
from backend.app.api.v1.auth import get_current_admin
from ai_engine.pipeline.video_source import build_video_source, validate_source_config

router = APIRouter(prefix="/cameras", tags=["Cameras"])
event_service = EventService()

class CameraCreateSchema(BaseModel):
    name: str
    location: str
    source_type: Literal["WEBCAM", "VIDEO_FILE", "RTSP"]
    source_url: str

    @model_validator(mode="after")
    def validate_source(self):
        validate_source_config(self.source_type, self.source_url)
        return self

class CameraUpdateSchema(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    source_type: Optional[Literal["WEBCAM", "VIDEO_FILE", "RTSP"]] = None
    source_url: Optional[str] = None

@router.get("")
def list_cameras():
    db = SessionLocal()
    try:
        cams = db.query(Camera).order_by(Camera.created_at.desc()).all()
        return [c.to_dict() for c in cams]
    finally:
        db.close()

@router.post("")
def create_camera(req: CameraCreateSchema, user: User = Depends(get_current_admin)):
    db = SessionLocal()
    try:
        cam = Camera(
            name=req.name,
            location=req.location,
            source_type=req.source_type,
            source_url=req.source_url,
            status="OFFLINE"
        )
        db.add(cam)
        db.flush()
        db.add(AuditLog(actor_user_id=user.id, action="CAMERA_CREATED", resource_type="camera", resource_id=cam.id, details=cam.name))
        db.commit()
        return cam.to_dict()
    finally:
        db.close()

@router.get("/{camera_id}")
def get_camera(camera_id: str):
    db = SessionLocal()
    try:
        cam = db.query(Camera).filter(Camera.id == camera_id).first()
        if not cam:
            raise HTTPException(status_code=404, detail="Camera not found")

        return cam.to_dict()
    finally:
        db.close()

@router.put("/{camera_id}")
def update_camera(camera_id: str, req: CameraUpdateSchema, user: User = Depends(get_current_admin)):
    db = SessionLocal()
    try:
        cam = db.query(Camera).filter(Camera.id == camera_id).first()
        if not cam:
            raise HTTPException(status_code=404, detail="Camera not found")
        next_type = req.source_type or cam.source_type
        next_url = req.source_url if req.source_url is not None else cam.source_url
        try:
            validate_source_config(next_type, next_url)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        if req.name is not None: cam.name = req.name
        if req.location is not None: cam.location = req.location
        cam.source_type = next_type
        cam.source_url = next_url
        db.add(AuditLog(actor_user_id=user.id, action="CAMERA_UPDATED", resource_type="camera", resource_id=cam.id, details=cam.name))
        db.commit()

        return cam.to_dict()
    finally:
        db.close()

@router.delete("/{camera_id}")
def delete_camera(camera_id: str, user: User = Depends(get_current_admin)):
    db = SessionLocal()
    try:
        cam = db.query(Camera).filter(Camera.id == camera_id).first()
        if not cam:
            raise HTTPException(status_code=404, detail="Camera not found")
        db.add(AuditLog(actor_user_id=user.id, action="CAMERA_DELETED", resource_type="camera", resource_id=cam.id, details=cam.name))
        db.delete(cam)
        db.commit()
        return {"success": True, "message": "Camera deleted"}
    finally:
        db.close()

@router.post("/{camera_id}/test")
def test_camera_connection(camera_id: str, user: User = Depends(get_current_admin)):
    db = SessionLocal()
    try:
        cam = db.query(Camera).filter(Camera.id == camera_id).first()
        if not cam:
            raise HTTPException(status_code=404, detail="Camera not found")
        previous_status = cam.status

        try:
            source = build_video_source(cam.source_type, cam.source_url)
            is_open = source.is_opened()
            if is_open:
                ret, _ = source.read_frame()
                is_open = ret
            source.release()
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

        cam.status = "ONLINE" if is_open else "OFFLINE"
        if is_open:
            cam.last_seen = datetime.now(timezone.utc)
        db.commit()

        if previous_status != cam.status:
            event_service.create_event(
                event_type="CAMERA_ONLINE" if is_open else "CAMERA_OFFLINE",
                camera_id=cam.id,
                location=cam.location,
                description="Camera connection test succeeded" if is_open else "Camera connection test failed",
            )

        return {
            "success": is_open,
            "status": cam.status,
            "message": "Camera connection successful" if is_open else "Failed to open camera source"
        }
    finally:
        db.close()
