from datetime import datetime, time as datetime_time, timedelta, timezone
from fastapi import APIRouter
from db.database import SessionLocal
from db.models import SecurityEvent, Camera, Alert

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get("")
def get_analytics():
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        today = now.date()
        start_day = today - timedelta(days=6)
        start = datetime.combine(start_day, datetime_time.min, tzinfo=timezone.utc)
        total_events = db.query(SecurityEvent).count()
        verified_count = db.query(SecurityEvent).filter(SecurityEvent.event_type.in_(["PERSON_VERIFIED", "PERSON_IDENTIFICATION_VERIFIED"])).count()
        unverified_count = db.query(SecurityEvent).filter(SecurityEvent.event_type.in_(["PERSON_UNVERIFIED", "UNKNOWN_PERSON", "PERSON_IDENTIFICATION_UNKNOWN"])).count()

        zone_breaches = db.query(SecurityEvent).filter(SecurityEvent.event_type.in_(["UNAUTHORIZED_ZONE_ACCESS", "RESTRICTED_ZONE_VIOLATION"])).count()
        crowd_incidents = db.query(SecurityEvent).filter(SecurityEvent.event_type == "CROWD_THRESHOLD_EXCEEDED").count()
        alerts_by_severity = [
            {"severity": severity, "count": db.query(Alert).filter(Alert.severity == severity).count()}
            for severity in ("INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL")
        ]
        alerts_by_status = [
            {"status": status, "count": db.query(Alert).filter(Alert.status == status).count()}
            for status in ("NEW", "ACKNOWLEDGED", "RESOLVED", "DISMISSED")
        ]

        # Group by camera
        cameras = db.query(Camera).all()
        events_by_camera = []
        for cam in cameras:
            c_count = db.query(SecurityEvent).filter(SecurityEvent.camera_id == cam.id).count()
            events_by_camera.append({"camera": cam.name, "events": c_count})

        # Build the series from persisted event timestamps; absent days are real zeros.
        recent_events = db.query(SecurityEvent).filter(SecurityEvent.timestamp >= start).all()
        by_day = {}
        zone_counts = {}
        for event in recent_events:
            event_time = event.timestamp
            event_day = event_time.astimezone(timezone.utc).date() if event_time.tzinfo else event_time.date()
            daily = by_day.get(event_day)
            if daily is None and event_day >= start_day:
                daily = {"verified": 0, "unverified": 0, "breaches": 0, "crowd": 0}
                by_day[event_day] = daily
            if daily is not None:
                if event.event_type in ("PERSON_VERIFIED", "PERSON_IDENTIFICATION_VERIFIED"):
                    daily["verified"] += 1
                elif event.event_type in ("PERSON_UNVERIFIED", "UNKNOWN_PERSON", "PERSON_IDENTIFICATION_UNKNOWN"):
                    daily["unverified"] += 1
                elif event.event_type in ("UNAUTHORIZED_ZONE_ACCESS", "RESTRICTED_ZONE_VIOLATION"):
                    daily["breaches"] += 1
                elif event.event_type == "CROWD_THRESHOLD_EXCEEDED":
                    daily["crowd"] += 1
            if event.event_type in ("UNAUTHORIZED_ZONE_ACCESS", "RESTRICTED_ZONE_VIOLATION") and event.location:
                zone_counts[event.location] = zone_counts.get(event.location, 0) + 1

        return {
            "total_events": total_events,
            "verified_count": verified_count,
            "unverified_count": unverified_count,
            "zone_breaches": zone_breaches,
            "crowd_incidents": crowd_incidents,
            "events_by_camera": events_by_camera,
            "events_by_zone": [{"zone": name, "events": count} for name, count in sorted(zone_counts.items())],
            "alerts_by_severity": alerts_by_severity,
            "alerts_by_status": alerts_by_status,
            "trends": [
                {"day": day.strftime("%a"), "date": day.isoformat(), **counts}
                for day, counts in sorted(by_day.items())
            ],
        }
    finally:
        db.close()
