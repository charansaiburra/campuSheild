import cv2 as cv
import numpy as np
import base64
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, Depends
from pydantic import BaseModel
from typing import Optional, List
from db.database import SessionLocal
from db.models import CollegeMember, FaceEmbedding, User, AuditLog
from services.enrollment_service import EnrollmentService
from backend.app.api.v1.auth import get_current_admin

router = APIRouter(prefix="/members", tags=["College Members"])
enrollment_service = EnrollmentService()

class MemberCreateSchema(BaseModel):
    name: str
    college_id: str
    role: str  # STUDENT, FACULTY, TEACHING_STAFF, NON_TEACHING_STAFF, SECURITY_STAFF, AUTHORIZED_VISITOR
    department: Optional[str] = "Computer Science"
    year: Optional[str] = "4th Year"
    email: Optional[str] = None

class MemberUpdateSchema(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    year: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = None

class Base64EnrollSchema(BaseModel):
    image_base64: str
    sample_label: Optional[str] = "Front"  # Front, Slight Left, Slight Right

@router.get("")
def list_members(
    role: Optional[str] = None,
    category: Optional[str] = None,
    department: Optional[str] = None,
    face_enrolled: Optional[bool] = None,
    search: Optional[str] = None,
    status: Optional[str] = None
):
    db = SessionLocal()
    try:
        query = db.query(CollegeMember)

        target_role = role or category
        if target_role and target_role.upper() != "ALL":
            target_upper = target_role.upper()
            if target_upper in ["STUDENT", "STUDENTS"]:
                query = query.filter(CollegeMember.role == "STUDENT")
            elif target_upper in ["FACULTY"]:
                query = query.filter(CollegeMember.role == "FACULTY")
            elif target_upper in ["STAFF"]:
                query = query.filter(CollegeMember.role.in_(["TEACHING_STAFF", "NON_TEACHING_STAFF", "SECURITY_STAFF", "STAFF"]))
            elif target_upper in ["VISITOR", "VISITORS", "AUTHORIZED_VISITOR"]:
                query = query.filter(CollegeMember.role.in_(["AUTHORIZED_VISITOR", "VISITOR"]))
            else:
                query = query.filter(CollegeMember.role == target_role)

        if department and department.upper() != "ALL":
            query = query.filter(CollegeMember.department == department)

        if face_enrolled is not None:
            query = query.filter(CollegeMember.face_enrolled == face_enrolled)

        if status and status.upper() != "ALL":
            query = query.filter(CollegeMember.status == status)
        elif not status:
            query = query.filter(CollegeMember.status == "ACTIVE")

        if search:
            search_pattern = f"%{search.strip()}%"
            query = query.filter(
                (CollegeMember.name.ilike(search_pattern)) |
                (CollegeMember.college_id.ilike(search_pattern))
            )

        members = query.order_by(CollegeMember.created_at.desc()).all()
        return [m.to_dict() for m in members]
    finally:
        db.close()

@router.post("")
def create_member(req: MemberCreateSchema, user: User = Depends(get_current_admin)):
    db = SessionLocal()
    try:
        existing = db.query(CollegeMember).filter(CollegeMember.college_id == req.college_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Member with this College ID already exists")

        member = CollegeMember(
            name=req.name,
            college_id=req.college_id,
            role=req.role,
            department=req.department,
            year=req.year,
            email=req.email,
            status="ACTIVE",
            face_enrolled=False
        )
        db.add(member)
        db.flush()
        db.add(AuditLog(actor_user_id=user.id, action="MEMBER_CREATED", resource_type="college_member", resource_id=member.id, details=member.college_id))
        db.commit()
        return member.to_dict()
    finally:
        db.close()

@router.get("/{member_id}")
def get_member(member_id: str):
    db = SessionLocal()
    try:
        member = db.query(CollegeMember).filter(CollegeMember.id == member_id).first()
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")
        return member.to_dict()
    finally:
        db.close()

@router.put("/{member_id}")
def update_member(member_id: str, req: MemberUpdateSchema, user: User = Depends(get_current_admin)):
    db = SessionLocal()
    try:
        member = db.query(CollegeMember).filter(CollegeMember.id == member_id).first()
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")
        if req.name: member.name = req.name
        if req.role: member.role = req.role
        if req.department: member.department = req.department
        if req.year: member.year = req.year
        if req.email: member.email = req.email
        if req.status: member.status = req.status
        db.add(AuditLog(actor_user_id=user.id, action="MEMBER_UPDATED", resource_type="college_member", resource_id=member.id, details=member.college_id))
        db.commit()
        return member.to_dict()
    finally:
        db.close()

@router.delete("/{member_id}")
def delete_member(member_id: str, user: User = Depends(get_current_admin)):
    db = SessionLocal()
    try:
        member = db.query(CollegeMember).filter(CollegeMember.id == member_id).first()
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")
        sample_rows = db.query(FaceEmbedding).filter(FaceEmbedding.member_id == member.id).all()
        enrollment_root = Path(os.path.abspath(os.path.join("data", "enrollments")))
        crop_paths = []
        for sample in sample_rows:
            if sample.crop_path:
                crop = Path(os.path.abspath(sample.crop_path))
                try:
                    crop.relative_to(enrollment_root)
                    crop_paths.append(crop)
                except ValueError:
                    continue
            db.delete(sample)
        member.face_enrolled = False
        member.status = "INACTIVE"
        db.add(AuditLog(actor_user_id=user.id, action="MEMBER_DEACTIVATED_AND_BIOMETRICS_REMOVED", resource_type="college_member", resource_id=member.id, details=member.college_id))
        db.commit()
        failed_crop_deletions = 0
        for crop in crop_paths:
            try:
                crop.unlink(missing_ok=True)
            except OSError:
                failed_crop_deletions += 1
        message = "Member deactivated; historical records were retained and face templates removed."
        if failed_crop_deletions:
            message += f" {failed_crop_deletions} face crop file(s) could not be deleted from disk."
        return {"success": True, "status": member.status, "message": message}
    finally:
        db.close()

@router.get("/{member_id}/samples")
def get_member_samples(member_id: str, user: User = Depends(get_current_admin)):
    db = SessionLocal()
    try:
        member = db.query(CollegeMember).filter(CollegeMember.id == member_id).first()
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")
        samples = db.query(FaceEmbedding).filter(FaceEmbedding.member_id == member.id).all()
        return [s.to_dict() for s in samples]
    finally:
        db.close()

@router.post("/{member_id}/enroll-face")
async def enroll_member_face(
    member_id: str,
    file: Optional[UploadFile] = File(None),
    image_base64: Optional[str] = Form(None),
    sample_label: Optional[str] = Form(None),
    user: User = Depends(get_current_admin),
):
    db = SessionLocal()
    try:
        member = db.query(CollegeMember).filter(CollegeMember.id == member_id).first()
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")

        img = None
        label = sample_label or "Front"

        # 1. Process uploaded file via multipart/form-data
        if file is not None:
            contents = await file.read()
            nparr = np.frombuffer(contents, np.uint8)
            img = cv.imdecode(nparr, cv.IMREAD_COLOR)
        # 2. Process form image_base64
        elif image_base64:
            try:
                img_data = base64.b64decode(image_base64.split(",")[-1])
                nparr = np.frombuffer(img_data, np.uint8)
                img = cv.imdecode(nparr, cv.IMREAD_COLOR)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid base64 image data")

        if img is None or img.size == 0:
            raise HTTPException(status_code=400, detail="No image file or base64 data provided.")

        res = enrollment_service.enroll_member_sample(
            member_id_or_college_id=member.id,
            image_input=img,
            sample_label=label
        )

        if not res.get("success"):
            raise HTTPException(status_code=400, detail=res.get("error", "Enrollment failed"))

        db.add(AuditLog(actor_user_id=user.id, action="FACE_SAMPLE_ENROLLED", resource_type="college_member", resource_id=member.id, details=f"sample_label={label}"))
        db.commit()

        return {
            "success": True,
            "member_id": member.id,
            "face_enrolled": True,
            "sample_count": res.get("sample_count"),
            "quality": "good",
            "quality_score": res.get("quality_score"),
            "message": f"Face sample '{label}' enrolled successfully for {member.name}"
        }
    finally:
        db.close()

@router.delete("/{member_id}/samples/{sample_id}")
def delete_sample(member_id: str, sample_id: str, user: User = Depends(get_current_admin)):
    db = SessionLocal()
    try:
        sample = db.query(FaceEmbedding).filter(FaceEmbedding.id == sample_id, FaceEmbedding.member_id == member_id).first()
        if not sample:
            raise HTTPException(status_code=404, detail="Sample not found")

        db.delete(sample)
        # Update face_enrolled flag if 0 samples remain
        remaining = db.query(FaceEmbedding).filter(FaceEmbedding.member_id == member_id).count() - 1
        if remaining <= 0:
            member = db.query(CollegeMember).filter(CollegeMember.id == member_id).first()
            if member: member.face_enrolled = False

        db.add(AuditLog(actor_user_id=user.id, action="FACE_SAMPLE_DELETED", resource_type="college_member", resource_id=member_id, details=f"sample_id={sample_id}"))

        db.commit()
        return {"success": True, "message": "Sample deleted"}
    finally:
        db.close()
