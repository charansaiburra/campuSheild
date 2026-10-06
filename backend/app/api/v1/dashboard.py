from fastapi import APIRouter
from datetime import datetime, timezone
from db.database import SessionLocal
from db.models import Camera, CollegeMember, SecurityEvent, Alert

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/summary")
def get_dashboard_summary():
    db = SessionLocal()
    try:
        total_cameras = db.query(Camera).count()
        online_cameras = db.query(Camera).filter(Camera.status == "ONLINE").count()
        offline_cameras = total_cameras - online_cameras

        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        today_events_count = db.query(SecurityEvent).filter(SecurityEvent.timestamp >= today_start).count()
        verified_count = db.query(SecurityEvent).filter(SecurityEvent.event_type.in_(["PERSON_VERIFIED", "PERSON_IDENTIFICATION_VERIFIED"])).count()
        unverified_count = db.query(SecurityEvent).filter(SecurityEvent.event_type.in_(["PERSON_UNVERIFIED", "UNKNOWN_PERSON", "PERSON_IDENTIFICATION_UNKNOWN"])).count()
        active_alerts_count = db.query(Alert).filter(Alert.status.in_(["NEW", "ACKNOWLEDGED"])).count()

        recent_events = db.query(SecurityEvent).order_by(SecurityEvent.timestamp.desc()).limit(10).all()

        # Events by type chart data
        event_types = ["PERSON_VERIFIED", "PERSON_UNVERIFIED", "UNKNOWN_PERSON", "PERSON_IDENTIFICATION_VERIFIED", "PERSON_IDENTIFICATION_UNKNOWN", "CROWD_THRESHOLD_EXCEEDED", "UNAUTHORIZED_ZONE_ACCESS", "AUTHORIZED_ZONE_ACCESS", "CAMERA_ONLINE", "CAMERA_OFFLINE"]
        events_by_type = []
        for et in event_types:
            count = db.query(SecurityEvent).filter(SecurityEvent.event_type == et).count()
            events_by_type.append({"type": et.replace("_", " "), "count": count})

        return {
            "cards": {
                "total_cameras": total_cameras,
                "online_cameras": online_cameras,
                "offline_cameras": offline_cameras,
                "people_detected": verified_count + unverified_count,
                "verified_persons": verified_count,
                "unverified_persons": unverified_count,
                "active_alerts": active_alerts_count,
                "today_events": today_events_count
            },
            "recent_events": [e.to_dict() for e in recent_events],
            "charts": {
                "events_by_type": events_by_type,
                "verified_vs_unverified": [
                    {"category": "Verified", "count": verified_count},
                    {"category": "Unverified", "count": unverified_count}
                ]
            }
        }
    finally:
        db.close()
