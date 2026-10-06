from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from db.database import SessionLocal
from db.models import Camera, Notification, NotificationLog, SecurityEvent, timestamp_iso_utc


class NotificationService:
    def list(self, unread_only: bool = False, limit: int = 100) -> List[Dict[str, Any]]:
        db = SessionLocal()
        try:
            query = db.query(Notification).filter(Notification.read_at.is_(None)) if unread_only else db.query(Notification)
            items = query.order_by(Notification.created_at.desc()).limit(limit).all()
            result = []
            for item in items:
                event = db.query(SecurityEvent).filter(SecurityEvent.id == item.event_id).first()
                camera = db.query(Camera).filter(Camera.id == event.camera_id).first() if event and event.camera_id else None
                payload = item.to_dict(
                    location=event.location if event else None,
                    camera_name=camera.name if camera else None,
                )
                payload["email_delivery"] = [
                    {"recipient": log.recipient, "status": log.delivery_status, "attempted_at": timestamp_iso_utc(log.attempted_at), "error": log.error}
                    for log in db.query(NotificationLog).filter(NotificationLog.notification_id == item.id).order_by(NotificationLog.attempted_at.desc()).all()
                ]
                result.append(payload)
            return result
        finally:
            db.close()

    def unread_count(self) -> int:
        db = SessionLocal()
        try:
            return db.query(Notification).filter(Notification.read_at.is_(None)).count()
        finally:
            db.close()

    def mark_read(self, notification_id: str) -> Optional[Dict[str, Any]]:
        db = SessionLocal()
        try:
            item = db.query(Notification).filter(Notification.id == notification_id).first()
            if not item:
                return None
            if item.read_at is None:
                item.read_at = datetime.now(timezone.utc)
                db.commit()
            event = db.query(SecurityEvent).filter(SecurityEvent.id == item.event_id).first()
            camera = db.query(Camera).filter(Camera.id == event.camera_id).first() if event and event.camera_id else None
            return item.to_dict(location=event.location if event else None, camera_name=camera.name if camera else None)
        finally:
            db.close()

    def mark_all_read(self) -> int:
        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            result = db.query(Notification).filter(Notification.read_at.is_(None)).update(
                {Notification.read_at: now}, synchronize_session=False
            )
            db.commit()
            return result
        finally:
            db.close()
