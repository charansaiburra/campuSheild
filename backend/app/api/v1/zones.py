from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from db.database import SessionLocal
from db.models import RestrictedZone, User, Camera, AuditLog
from backend.app.api.v1.auth import get_current_admin

router = APIRouter(prefix="/zones", tags=["Restricted Zones"])

class ZoneCreateSchema(BaseModel):
    camera_id: str
    name: str
    zone_type: Optional[str] = "RESTRICTED"
    polygon: List[List[float]]
    allowed_roles: List[str]
    occupancy_threshold: Optional[int] = Field(10, ge=1)
    is_active: Optional[bool] = True

    @field_validator("polygon")
    @classmethod
    def validate_polygon(cls, polygon):
        if len(polygon) < 3 or len(polygon) > 200 or any(len(point) != 2 for point in polygon):
            raise ValueError("A zone polygon must contain between 3 and 200 x/y points")
        if any(x < 0 or y < 0 for x, y in polygon):
            raise ValueError("Zone coordinates cannot be negative")
        return polygon

    @field_validator("allowed_roles")
    @classmethod
    def validate_allowed_roles(cls, roles):
        normalized = sorted({role.strip().upper() for role in roles if role and role.strip()})
        if not normalized:
            raise ValueError("At least one allowed role is required")
        return normalized

class ZoneUpdateSchema(BaseModel):
    name: Optional[str] = None
    polygon: Optional[List[List[float]]] = None
    allowed_roles: Optional[List[str]] = None
    occupancy_threshold: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None

    @field_validator("polygon")
    @classmethod
    def validate_polygon(cls, polygon):
        if polygon is not None and (len(polygon) < 3 or len(polygon) > 200 or any(len(point) != 2 for point in polygon)):
            raise ValueError("A zone polygon must contain between 3 and 200 x/y points")
        if polygon is not None and any(x < 0 or y < 0 for x, y in polygon):
            raise ValueError("Zone coordinates cannot be negative")
        return polygon

    @field_validator("allowed_roles")
    @classmethod
    def validate_allowed_roles(cls, roles):
        if roles is not None and not any(role and role.strip() for role in roles):
            raise ValueError("At least one allowed role is required")
        return sorted({role.strip().upper() for role in roles if role and role.strip()}) if roles is not None else None

@router.get("")
def list_zones(camera_id: Optional[str] = None):
    db = SessionLocal()
    try:
        query = db.query(RestrictedZone)
        if camera_id: query = query.filter(RestrictedZone.camera_id == camera_id)
        zones = query.order_by(RestrictedZone.created_at.desc()).all()
        return [z.to_dict() for z in zones]
    finally:
        db.close()

@router.post("")
def create_zone(req: ZoneCreateSchema, user: User = Depends(get_current_admin)):
    db = SessionLocal()
    try:
        if not db.query(Camera.id).filter(Camera.id == req.camera_id).first():
            raise HTTPException(status_code=404, detail="Camera not found")
        zone = RestrictedZone(
            camera_id=req.camera_id,
            name=req.name,
            zone_type=req.zone_type,
            occupancy_threshold=req.occupancy_threshold,
            is_active=req.is_active
        )
        zone.set_polygon(req.polygon)
        zone.set_allowed_roles(req.allowed_roles)
        db.add(zone)
        db.add(AuditLog(actor_user_id=user.id, action="ZONE_CREATED", resource_type="restricted_zone", details=zone.name))
        db.commit()
        return zone.to_dict()
    finally:
        db.close()

@router.put("/{zone_id}")
def update_zone(zone_id: str, req: ZoneUpdateSchema, user: User = Depends(get_current_admin)):
    db = SessionLocal()
    try:
        zone = db.query(RestrictedZone).filter(RestrictedZone.id == zone_id).first()
        if not zone:
            raise HTTPException(status_code=404, detail="Zone not found")
        if req.name is not None: zone.name = req.name
        if req.polygon is not None: zone.set_polygon(req.polygon)
        if req.allowed_roles is not None: zone.set_allowed_roles(req.allowed_roles)
        if req.occupancy_threshold is not None: zone.occupancy_threshold = req.occupancy_threshold
        if req.is_active is not None: zone.is_active = req.is_active
        db.add(AuditLog(actor_user_id=user.id, action="ZONE_UPDATED", resource_type="restricted_zone", resource_id=zone.id, details=zone.name))
        db.commit()
        return zone.to_dict()
    finally:
        db.close()

@router.delete("/{zone_id}")
def delete_zone(zone_id: str, user: User = Depends(get_current_admin)):
    db = SessionLocal()
    try:
        zone = db.query(RestrictedZone).filter(RestrictedZone.id == zone_id).first()
        if not zone:
            raise HTTPException(status_code=404, detail="Zone not found")
        db.add(AuditLog(actor_user_id=user.id, action="ZONE_DELETED", resource_type="restricted_zone", resource_id=zone.id, details=zone.name))
        db.delete(zone)
        db.commit()
        return {"success": True, "message": "Zone deleted"}
    finally:
        db.close()
