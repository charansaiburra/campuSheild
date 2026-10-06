from typing import List, Dict, Any, Optional
from db.database import SessionLocal
from datetime import datetime, timezone
from db.models import Alert, SecurityEvent, Camera, Notification, AuditLog

class AlertService:
    def get_alerts(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        db = SessionLocal()
        try:
            query = db.query(Alert)
            if status:
                query = query.filter(Alert.status == status)
            if severity:
                query = query.filter(Alert.severity == severity)

            alerts = query.order_by(Alert.timestamp.desc()).limit(limit).all()
            results = []
            for alert in alerts:
                item = alert.to_dict()
                event = db.query(SecurityEvent).filter(SecurityEvent.id == alert.event_id).first() if alert.event_id else None
                camera = db.query(Camera).filter(Camera.id == alert.camera_id).first() if alert.camera_id else None
                item.update({
                    "event_type": event.event_type if event else None,
                    "track_id": event.track_id if event else None,
                    "member_id": event.member_id if event else None,
                    "member_name": event.member.name if event and event.member else None,
                    "location": event.location if event else (camera.location if camera else None),
                    "camera_name": camera.name if camera else None,
                    "snapshot_path": event.snapshot_path if event else None,
                })
                results.append(item)
            return results
        finally:
            db.close()

    def update_alert_status(self, alert_id: str, new_status: str, actor_user_id: str) -> Optional[Dict[str, Any]]:
        if new_status not in ["NEW", "ACKNOWLEDGED", "RESOLVED", "DISMISSED"]:
            return None

        db = SessionLocal()
        try:
            alert = db.query(Alert).filter(Alert.id == alert_id).first()
            if not alert:
                return None

            now = datetime.now(timezone.utc)
            alert.status = new_status
            if new_status == "ACKNOWLEDGED" and alert.acknowledged_at is None:
                alert.acknowledged_at = now
            if new_status in ["RESOLVED", "DISMISSED"] and alert.resolved_at is None:
                alert.resolved_at = now
            if alert.event_id:
                event = db.query(SecurityEvent).filter(SecurityEvent.id == alert.event_id).first()
                if event:
                    event.status = new_status
                    if new_status == "ACKNOWLEDGED" and event.acknowledged_at is None:
                        event.acknowledged_at = now
                    if new_status in ["RESOLVED", "DISMISSED"] and event.resolved_at is None:
                        event.resolved_at = now

            notification = db.query(Notification).filter(Notification.alert_id == alert.id).first()
            if notification and new_status != "NEW" and notification.read_at is None:
                notification.read_at = now
            db.add(AuditLog(
                actor_user_id=actor_user_id,
                action=f"ALERT_{new_status}",
                resource_type="alert",
                resource_id=alert.id,
                details=f"Alert status changed to {new_status}",
                created_at=now,
            ))

            db.commit()
            print(f"[AlertService] Updated alert {alert_id} status to {new_status}")
            return alert.to_dict()
        except Exception as e:
            db.rollback()
            print(f"[AlertService] Error updating alert: {e}")
            return None
        finally:
            db.close()
