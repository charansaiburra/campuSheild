import cv2 as cv
import numpy as np
import base64
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional
from db.database import SessionLocal
from db.models import CollegeMember, SecurityEvent
from services.enrollment_service import EnrollmentService
from ai_engine.face.face_embedder import FaceEmbedder
from ai_engine.face.face_verifier import FaceVerifier

router = APIRouter(prefix="/person-identification", tags=["Person Identification"])


def _utc_timestamp_iso(timestamp: datetime) -> str:
    """Serialize stored identification audit timestamps as explicit UTC."""
    if timestamp.tzinfo is None:
        # Existing SQLite rows are naive but were generated with datetime.utcnow().
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    else:
        timestamp = timestamp.astimezone(timezone.utc)
    return timestamp.isoformat().replace("+00:00", "Z")

enrollment_service = EnrollmentService()
embedder = FaceEmbedder()
verifier = FaceVerifier()

@router.post("")
async def identify_person(
    file: Optional[UploadFile] = File(None),
    image_base64: Optional[str] = Form(None)
):
    # Capture the identification request time before image decoding or inference.
    request_timestamp = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        img = None

        # 1. Decode image from file upload or base64
        if file is not None:
            contents = await file.read()
            nparr = np.frombuffer(contents, np.uint8)
            img = cv.imdecode(nparr, cv.IMREAD_COLOR)
        elif image_base64:
            try:
                img_data = base64.b64decode(image_base64.split(",")[-1])
                nparr = np.frombuffer(img_data, np.uint8)
                img = cv.imdecode(nparr, cv.IMREAD_COLOR)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid base64 image data")

        if img is None or img.size == 0:
            return {
                "success": False,
                "status": "NO_FACE",
                "member": None,
                "similarity": 0.0,
                "message": "No face detected. Please upload a clear image containing a visible face."
            }

        # 2. Run Face Quality & Detection Validation
        val_res = enrollment_service.validate_and_extract_face(img)
        if not val_res.get("valid"):
            err_msg = val_res.get("error", "")
            if "No face detected" in err_msg:
                status_code = "NO_FACE"
                user_msg = "No face detected. Please upload a clear image containing a visible face."
            elif "Multiple faces detected" in err_msg:
                status_code = "MULTIPLE_FACES"
                user_msg = "Multiple faces detected. Please upload an image containing one person."
            elif "too small" in err_msg or "quality is too low" in err_msg:
                status_code = "POOR_QUALITY"
                user_msg = "Face quality is too low for reliable identification."
            else:
                status_code = "ERROR"
                user_msg = err_msg or "Unable to process the image."

            return {
                "success": False,
                "status": status_code,
                "member": None,
                "similarity": 0.0,
                "message": user_msg
            }

        face_crop = val_res.get("face_crop")
        if face_crop is None or face_crop.size == 0:
            return {
                "success": False,
                "status": "NO_FACE",
                "member": None,
                "similarity": 0.0,
                "message": "No face detected. Please upload a clear image containing a visible face."
            }

        # 3. Generate FaceNet 512-d embedding
        query_vec = embedder.generate_embedding(face_crop)
        if query_vec is None:
            return {
                "success": False,
                "status": "ERROR",
                "member": None,
                "similarity": 0.0,
                "message": "Failed to generate face representation."
            }

        # 4. Perform Cosine Similarity Search against Enrolled Database
        verifier.reload_enrolled_embeddings()
        ver_res = verifier.verify_embedding(query_vec)

        similarity = float(ver_res.get("similarity", 0.0))

        if ver_res.get("status") == "VERIFIED":
            member_id = ver_res.get("member_id")
            member = db.query(CollegeMember).filter(CollegeMember.id == member_id).first()

            if member:
                # Log audit event in database
                audit_event = SecurityEvent(
                    member_id=member.id,
                    event_type="PERSON_IDENTIFICATION_VERIFIED",
                    severity="INFO",
                    description=f"Person identification search verified member '{member.name}' ({member.college_id}) with similarity {similarity:.2f}",
                    status="CLOSED",
                    timestamp=request_timestamp,
                    similarity=similarity,
                )
                db.add(audit_event)
                db.commit()

                return {
                    "success": True,
                    "status": "VERIFIED",
                    "member": member.to_dict(),
                    "similarity": round(similarity, 4),
                    "message": f"Person identified as {member.name} ({member.college_id})."
                }

        # If similarity < threshold or status UNKNOWN/UNVERIFIED
        audit_event = SecurityEvent(
            event_type="PERSON_IDENTIFICATION_UNKNOWN",
            severity="INFO",
            description=f"Person identification search returned no match in enrolled database (best similarity: {similarity:.2f})",
            status="CLOSED",
            timestamp=request_timestamp,
            similarity=similarity,
        )
        db.add(audit_event)
        db.commit()

        return {
            "success": True,
            "status": "UNKNOWN",
            "member": None,
            "similarity": round(max(0.0, similarity), 4),
            "message": "No sufficiently reliable match was found in the enrolled college-member database."
        }
    finally:
        db.close()


@router.get("/history")
def get_identification_history():
    db = SessionLocal()
    try:
        events = db.query(SecurityEvent).filter(
            SecurityEvent.event_type.in_(["PERSON_IDENTIFICATION_VERIFIED", "PERSON_IDENTIFICATION_UNKNOWN"])
        ).order_by(SecurityEvent.timestamp.desc()).limit(20).all()

        history = []
        for e in events:
            history.append({
                "id": e.id,
                "timestamp": _utc_timestamp_iso(e.timestamp) if e.timestamp else None,
                "member_id": e.member_id,
                "similarity": e.similarity,
                "status": "VERIFIED" if e.event_type == "PERSON_IDENTIFICATION_VERIFIED" else "UNKNOWN",
                "member_name": e.member.name if e.member else "—",
                "college_id": e.member.college_id if e.member else "—",
                "description": e.description
            })
        return history
    finally:
        db.close()
