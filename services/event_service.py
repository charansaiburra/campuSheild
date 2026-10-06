import os
import cv2 as cv
import numpy as np
import smtplib
import ssl
from email.message import EmailMessage
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Optional, Dict
from db.database import SessionLocal
from db.models import SecurityEvent, Alert, SystemSetting, Notification, NotificationLog

DEFAULT_COOLDOWN_SECONDS = 15.0
EVENT_CREATE_LOCK = Lock()

SEVERITY_MAP = {
    "PERSON_VERIFIED": "INFO",
    "PERSON_UNVERIFIED": "MEDIUM",
    "UNKNOWN_PERSON": "MEDIUM",
    "PERSON_IDENTIFICATION_VERIFIED": "INFO",
    "PERSON_IDENTIFICATION_UNKNOWN": "INFO",
    "AUTHORIZED_ZONE_ACCESS": "INFO",
    "UNAUTHORIZED_ZONE_ACCESS": "HIGH",
    "CROWD_THRESHOLD_EXCEEDED": "MEDIUM",
    "CAMERA_ONLINE": "INFO",
    "CAMERA_OFFLINE": "HIGH"
}

class EventService:
    def create_event(
        self,
        event_type: str,
        camera_id: Optional[str] = None,
        zone_id: Optional[str] = None,
        track_id: Optional[int] = None,
        member_id: Optional[str] = None,
        location: Optional[str] = None,
        description: Optional[str] = None,
        frame_snapshot: Optional[np.ndarray] = None,
        cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS
    ) -> Optional[Dict[str, Any]]:
        """
        Creates a security event in DB with debouncing and optional snapshot saving.
        """
        severity = SEVERITY_MAP.get(event_type, "INFO")
        db = SessionLocal()
        try:
            # Honor configured alert cooldowns and persist the debounce across restarts.
            setting_key = {
                "CROWD_THRESHOLD_EXCEEDED": "CROWD_ALERT_COOLDOWN_SECONDS",
                "UNAUTHORIZED_ZONE_ACCESS": "ZONE_BREACH_COOLDOWN_SECONDS",
            }.get(event_type)
            setting = db.query(SystemSetting).filter(SystemSetting.key == setting_key).first() if setting_key else None
            effective_cooldown = cooldown_seconds
            if setting:
                try:
                    effective_cooldown = max(0.0, float(setting.value))
                except (TypeError, ValueError):
                    pass

            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(seconds=effective_cooldown)
            recent = db.query(SecurityEvent.id).filter(
                SecurityEvent.camera_id == camera_id,
                SecurityEvent.zone_id == zone_id,
                SecurityEvent.event_type == event_type,
                SecurityEvent.timestamp >= cutoff,
            )
            if location is not None:
                recent = recent.filter(SecurityEvent.location == location)
            if member_id is not None:
                recent = recent.filter(SecurityEvent.member_id == member_id)
            elif track_id is not None:
                recent = recent.filter(SecurityEvent.track_id == track_id)
            else:
                recent = recent.filter(SecurityEvent.member_id.is_(None), SecurityEvent.track_id.is_(None))
            with EVENT_CREATE_LOCK:
                if effective_cooldown and recent.first():
                    return None

                snapshot_path = None
                if frame_snapshot is not None and frame_snapshot.size > 0:
                    try:
                        snapshots_dir = os.path.join("data", "snapshots")
                        os.makedirs(snapshots_dir, exist_ok=True)
                        timestamp_str = now.strftime("%Y%m%d_%H%M%S_%f")
                        filename = f"{event_type}_{timestamp_str}.jpg"
                        candidate_path = os.path.join(snapshots_dir, filename)
                        if cv.imwrite(candidate_path, frame_snapshot):
                            snapshot_path = candidate_path
                        else:
                            print("[EventService] OpenCV could not write the event snapshot.")
                    except Exception as e:
                        print(f"[EventService] Error saving snapshot: {e}")

                event = SecurityEvent(
                    camera_id=camera_id,
                    zone_id=zone_id,
                    track_id=track_id,
                    member_id=member_id,
                    event_type=event_type,
                    severity=severity,
                    location=location,
                    description=description or event_type.replace("_", " ").title(),
                    snapshot_path=snapshot_path,
                    status="NEW" if severity in ["MEDIUM", "HIGH", "CRITICAL"] else "CLOSED",
                    timestamp=now,
                    created_at=now,
                )
                db.add(event)
                db.flush()

                # Alert rows are always backed by this actual event.
                alert_dict = None
                if severity in ["MEDIUM", "HIGH", "CRITICAL"]:
                    alert = Alert(
                        event_id=event.id,
                        camera_id=camera_id,
                        severity=severity,
                        title=f"ALERT: {event_type.replace('_', ' ')}",
                        description=description or event_type.replace("_", " ").title(),
                        status="NEW",
                        timestamp=now,
                    )
                    db.add(alert)
                    db.flush()
                    notification = Notification(
                        alert_id=alert.id,
                        event_id=event.id,
                        notification_type=event_type,
                        severity=severity,
                        title=alert.title,
                        description=alert.description,
                        created_at=now,
                    )
                    db.add(notification)
                    db.flush()
                    alert_dict = alert.to_dict()
                    notification_id = notification.id
                else:
                    notification_id = None

                db.commit()

                if notification_id:
                    self._deliver_email(notification_id, alert_dict["title"], alert_dict["description"] or "")

                res = event.to_dict()
                res["alert"] = alert_dict
                res["notification_created"] = notification_id is not None
                print(f"[EventService] Created security event: {event_type} (Severity: {severity})")
                return res
        except Exception as e:
            db.rollback()
            print(f"[EventService] Error creating event: {e}")
            return None
        finally:
            db.close()

    @staticmethod
    def _deliver_email(notification_id: str, title: str, description: str) -> None:
        recipients = [item.strip() for item in os.getenv("ALERT_EMAIL_RECIPIENTS", "").split(",") if item.strip()]
        host = os.getenv("SMTP_HOST", "").strip()
        port_value = os.getenv("SMTP_PORT", "").strip()
        sender = os.getenv("SMTP_FROM", "").strip()
        username = os.getenv("SMTP_USERNAME", "").strip()
        password = os.getenv("SMTP_PASSWORD", "")
        configured = bool(recipients and host and port_value and sender and ((username and password) or (not username and not password)))

        if not configured:
            db = SessionLocal()
            try:
                db.add(NotificationLog(
                    notification_id=notification_id,
                    delivery_status="NOT_CONFIGURED",
                    error="SMTP host, port, sender, recipients, or matching credentials are not configured.",
                ))
                db.commit()
            except Exception:
                db.rollback()
            finally:
                db.close()
            return

        try:
            port = int(port_value)
        except ValueError:
            port = -1
        if port <= 0 or port > 65535:
            recipients_to_attempt = [(recipient, "FAILED", "SMTP_PORT is invalid.") for recipient in recipients]
        else:
            recipients_to_attempt = []
            for recipient in recipients:
                status = "SENT"
                error_text = None
                try:
                    message = EmailMessage()
                    message["Subject"] = title
                    message["From"] = sender
                    message["To"] = recipient
                    message.set_content(description)
                    if port == 465:
                        with smtplib.SMTP_SSL(host, port, timeout=15, context=ssl.create_default_context()) as client:
                            if username:
                                client.login(username, password)
                            client.send_message(message)
                    else:
                        with smtplib.SMTP(host, port, timeout=15) as client:
                            client.ehlo()
                            if os.getenv("SMTP_USE_TLS", "true").strip().lower() in {"1", "true", "yes"}:
                                client.starttls(context=ssl.create_default_context())
                                client.ehlo()
                            if username:
                                client.login(username, password)
                            client.send_message(message)
                except Exception as exc:
                    status = "FAILED"
                    error_text = f"{type(exc).__name__}: {str(exc)[:500]}"
                recipients_to_attempt.append((recipient, status, error_text))

        db = SessionLocal()
        try:
            for recipient, status, error_text in recipients_to_attempt:
                db.add(NotificationLog(
                    notification_id=notification_id,
                    recipient=recipient,
                    delivery_status=status,
                    error=error_text,
                ))
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
