import json
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from db.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def timestamp_iso_utc(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(30), default="SECURITY_OFFICER")  # ADMIN, SECURITY_OFFICER
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": timestamp_iso_utc(self.created_at)
        }


class CollegeMember(Base):
    __tablename__ = "college_members"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    college_id = Column(String(50), unique=True, nullable=False)
    role = Column(String(50), nullable=False)  # STUDENT, FACULTY, TEACHING_STAFF, NON_TEACHING_STAFF, SECURITY_STAFF, AUTHORIZED_VISITOR
    department = Column(String(100), nullable=True)
    year = Column(String(20), nullable=True)
    email = Column(String(100), nullable=True)
    status = Column(String(20), default="ACTIVE")  # ACTIVE, INACTIVE
    face_enrolled = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    embeddings = relationship("FaceEmbedding", back_populates="member", cascade="all, delete-orphan")
    events = relationship("SecurityEvent", back_populates="member")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "college_id": self.college_id,
            "role": self.role,
            "department": self.department,
            "year": self.year,
            "email": self.email,
            "status": self.status,
            "face_enrolled": self.face_enrolled,
            "sample_count": len(self.embeddings) if self.embeddings else 0,
            "created_at": timestamp_iso_utc(self.created_at)
        }


class FaceEmbedding(Base):
    __tablename__ = "face_embeddings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    member_id = Column(String(36), ForeignKey("college_members.id"), nullable=False)
    sample_label = Column(String(50), default="Front")  # Front, Left, Right, etc.
    embedding_json = Column(Text, nullable=False)
    quality_score = Column(Float, default=1.0)
    crop_path = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    member = relationship("CollegeMember", back_populates="embeddings")

    def set_embedding(self, embedding_list):
        self.embedding_json = json.dumps(embedding_list)

    def get_embedding(self):
        return json.loads(self.embedding_json)

    def to_dict(self):
        return {
            "id": self.id,
            "member_id": self.member_id,
            "sample_label": self.sample_label,
            "quality_score": self.quality_score,
            "created_at": timestamp_iso_utc(self.created_at)
        }


class Camera(Base):
    __tablename__ = "cameras"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    location = Column(String(100), nullable=False)
    source_type = Column(String(20), nullable=False)  # WEBCAM, VIDEO_FILE, RTSP
    source_url = Column(String(255), nullable=False)  # "0", "test_datas/testing_video.mp4", "rtsp://..."
    status = Column(String(20), default="OFFLINE")    # ONLINE, OFFLINE, ERROR
    last_seen = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    zones = relationship("RestrictedZone", back_populates="camera", cascade="all, delete-orphan")
    events = relationship("SecurityEvent", back_populates="camera")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "location": self.location,
            "source_type": self.source_type,
            "status": self.status,
            "last_seen": timestamp_iso_utc(self.last_seen),
            "created_at": timestamp_iso_utc(self.created_at)
        }


class RestrictedZone(Base):
    __tablename__ = "restricted_zones"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    camera_id = Column(String(36), ForeignKey("cameras.id"), nullable=False)
    name = Column(String(100), nullable=False)
    zone_type = Column(String(50), default="RESTRICTED")  # RESTRICTED, CROWD_MONITORED
    polygon_json = Column(Text, nullable=False)           # JSON array of [x, y] coordinates
    allowed_roles_json = Column(Text, nullable=False)     # JSON array of allowed role strings
    occupancy_threshold = Column(Integer, default=10)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    camera = relationship("Camera", back_populates="zones")

    def get_polygon(self):
        return json.loads(self.polygon_json) if self.polygon_json else []

    def set_polygon(self, poly_list):
        self.polygon_json = json.dumps(poly_list)

    def get_allowed_roles(self):
        return json.loads(self.allowed_roles_json) if self.allowed_roles_json else []

    def set_allowed_roles(self, roles_list):
        self.allowed_roles_json = json.dumps(roles_list)

    def to_dict(self):
        return {
            "id": self.id,
            "camera_id": self.camera_id,
            "name": self.name,
            "zone_type": self.zone_type,
            "polygon": self.get_polygon(),
            "allowed_roles": self.get_allowed_roles(),
            "occupancy_threshold": self.occupancy_threshold,
            "is_active": self.is_active,
            "created_at": timestamp_iso_utc(self.created_at)
        }


class SecurityEvent(Base):
    __tablename__ = "security_events"
    __table_args__ = (
        Index("ix_security_events_timestamp", "timestamp"),
        Index("ix_security_events_type_timestamp", "event_type", "timestamp"),
        Index("ix_security_events_status_timestamp", "status", "timestamp"),
        Index("ix_security_events_camera_timestamp", "camera_id", "timestamp"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    camera_id = Column(String(36), ForeignKey("cameras.id"), nullable=True)
    zone_id = Column(String(36), ForeignKey("restricted_zones.id"), nullable=True)
    track_id = Column(Integer, nullable=True)
    member_id = Column(String(36), ForeignKey("college_members.id"), nullable=True)
    event_type = Column(String(50), nullable=False)
    severity = Column(String(20), default="INFO")
    location = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    snapshot_path = Column(String(255), nullable=True)
    status = Column(String(20), default="NEW")
    timestamp = Column(DateTime(timezone=True), default=utc_now)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    similarity = Column(Float, nullable=True)

    camera = relationship("Camera", back_populates="events")
    member = relationship("CollegeMember", back_populates="events")

    def to_dict(self):
        return {
            "id": self.id,
            "camera_id": self.camera_id,
            "zone_id": self.zone_id,
            "track_id": self.track_id,
            "similarity": self.similarity,
            "member_id": self.member_id,
            "member_name": self.member.name if self.member else None,
            "event_type": self.event_type,
            "severity": self.severity,
            "location": self.location,
            "description": self.description,
            "snapshot_path": self.snapshot_path,
            "status": self.status,
            "timestamp": timestamp_iso_utc(self.timestamp),
            "created_at": timestamp_iso_utc(self.created_at),
            "acknowledged_at": timestamp_iso_utc(self.acknowledged_at),
            "resolved_at": timestamp_iso_utc(self.resolved_at),
        }


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_status_timestamp", "status", "timestamp"),
        Index("ix_alerts_severity_timestamp", "severity", "timestamp"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String(36), ForeignKey("security_events.id"), nullable=True)
    camera_id = Column(String(36), ForeignKey("cameras.id"), nullable=True)
    severity = Column(String(20), default="MEDIUM")
    title = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(20), default="NEW")
    timestamp = Column(DateTime(timezone=True), default=utc_now)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "event_id": self.event_id,
            "camera_id": self.camera_id,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "timestamp": timestamp_iso_utc(self.timestamp),
            "acknowledged_at": timestamp_iso_utc(self.acknowledged_at),
            "resolved_at": timestamp_iso_utc(self.resolved_at),
        }


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_read_created", "read_at", "created_at"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    alert_id = Column(String(36), ForeignKey("alerts.id"), nullable=False, unique=True)
    event_id = Column(String(36), ForeignKey("security_events.id"), nullable=False)
    notification_type = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False)
    title = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    read_at = Column(DateTime(timezone=True), nullable=True)

    def to_dict(self, location=None, camera_name=None):
        return {
            "id": self.id,
            "alert_id": self.alert_id,
            "event_id": self.event_id,
            "type": self.notification_type,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "timestamp": timestamp_iso_utc(self.created_at),
            "read_at": timestamp_iso_utc(self.read_at),
            "is_read": self.read_at is not None,
            "location": location,
            "camera_name": camera_name,
        }


class NotificationLog(Base):
    __tablename__ = "notification_logs"
    __table_args__ = (Index("ix_notification_logs_notification_attempt", "notification_id", "attempted_at"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    notification_id = Column(String(36), ForeignKey("notifications.id"), nullable=False)
    recipient = Column(String(255), nullable=True)
    attempted_at = Column(DateTime(timezone=True), default=utc_now)
    delivery_status = Column(String(30), nullable=False)
    error = Column(Text, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_created_at", "created_at"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    actor_user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(36), nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
    description = Column(String(255), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utc_now)

    def to_dict(self):
        return {
            "key": self.key,
            "value": self.value,
            "description": self.description,
            "updated_at": timestamp_iso_utc(self.updated_at)
        }
