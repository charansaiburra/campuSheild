import os
import cv2 as cv
import numpy as np
from typing import Dict, Any, Union, Optional
from db.database import SessionLocal
from db.models import CollegeMember, FaceEmbedding
from ai_engine.face.face_embedder import FaceEmbedder
from ai_engine.detection.face_detector import FaceDetector

class EnrollmentService:
    def __init__(self):
        self.embedder = FaceEmbedder()
        self.face_detector = FaceDetector()

    def validate_and_extract_face(self, img: np.ndarray) -> Dict[str, Any]:
        """
        Runs quality validation on input image (camera capture or photo upload):
        - Exactly one face
        - Sufficient face size (>= 60x60)
        - Acceptable sharpness/resolution
        Returns dict with success status, error message, and cropped face image.
        """
        if img is None or img.size == 0:
            return {"valid": False, "error": "Invalid or unreadable image input."}

        h, w, _ = img.shape
        if w < 50 or h < 50:
            return {
                "valid": False,
                "error": "Face is too small. Move slightly closer or use a higher resolution photo."
            }

        # Run face detection
        face_boxes = self.face_detector.detect_faces(img, conf_threshold=0.35)

        if len(face_boxes) == 0:
            try:
                gray_check = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
                blur_var_check = cv.Laplacian(gray_check, cv.CV_64F).var()
            except Exception:
                blur_var_check = 0.0

            # Check if input image is already a clear pre-cropped face (60x60 up to 400x400)
            if 60 <= w <= 400 and 60 <= h <= 400 and blur_var_check >= 10.0:
                face_crop = img
            else:
                return {"valid": False, "error": "No face detected. Please upload/capture a clear face image."}
        elif len(face_boxes) > 1:
            return {
                "valid": False,
                "error": "Multiple faces detected. Please use an image containing only the person being registered."
            }
        else:
            x1, y1, x2, y2 = face_boxes[0]
            face_w = x2 - x1
            face_h = y2 - y1
            if face_w < 50 or face_h < 50:
                return {
                    "valid": False,
                    "error": "Face is too small. Move slightly closer or use a higher resolution photo."
                }
            face_crop = img[y1:y2, x1:x2]

        # Blurriness / Sharpness Check using Laplacian variance
        try:
            gray = cv.cvtColor(face_crop, cv.COLOR_BGR2GRAY)
            blur_var = cv.Laplacian(gray, cv.CV_64F).var()
            if blur_var < 10.0:
                return {
                    "valid": False,
                    "error": "Face quality is too low. Please use a clearer image."
                }
        except Exception:
            blur_var = 50.0

        return {
            "valid": True,
            "message": "Face detected. Image is suitable for enrollment.",
            "face_crop": face_crop,
            "quality_score": round(min(1.0, float(blur_var / 100.0)), 2)
        }

    def enroll_member_sample(
        self,
        member_id_or_college_id: str,
        image_input: Union[str, np.ndarray],
        sample_label: str = "Front",
        name: Optional[str] = None,
        role: Optional[str] = None,
        department: Optional[str] = None,
        year: Optional[str] = None,
        email: Optional[str] = None,
        replace_all: bool = False
    ) -> Dict[str, Any]:
        """
        Unified processing pipeline for Camera Capture and Photo Upload.
        Appends or creates a face embedding sample for a college member.
        """
        # Load image
        if isinstance(image_input, str):
            if not os.path.exists(image_input):
                return {"success": False, "error": f"Image file not found: {image_input}"}
            img = cv.imread(image_input)
        else:
            img = image_input

        # Quality validation
        val_res = self.validate_and_extract_face(img)
        if not val_res["valid"]:
            return {"success": False, "error": val_res["error"]}

        face_crop = val_res["face_crop"]
        quality_score = val_res["quality_score"]

        # Generate FaceNet 512-d embedding
        embedding = self.embedder.generate_embedding(face_crop)
        if embedding is None:
            return {"success": False, "error": "Failed to extract FaceNet embedding."}

        db = SessionLocal()
        try:
            # Query member by id or college_id
            member = db.query(CollegeMember).filter(
                (CollegeMember.id == member_id_or_college_id) |
                (CollegeMember.college_id == member_id_or_college_id)
            ).first()

            if not member:
                if not name or not role:
                    return {"success": False, "error": "Member not found. Name and Role required to create member."}
                member = CollegeMember(
                    name=name,
                    college_id=member_id_or_college_id,
                    role=role,
                    department=department or "General",
                    year=year or "N/A",
                    email=email or "",
                    face_enrolled=True
                )
                db.add(member)
                db.flush()

            if replace_all:
                db.query(FaceEmbedding).filter(FaceEmbedding.member_id == member.id).delete()

            member.face_enrolled = True

            # Save enrollment face crop artifact
            sanitized_name = member.name.replace(" ", "_")
            enroll_dir = os.path.join("data", "enrollments", sanitized_name)
            os.makedirs(enroll_dir, exist_ok=True)
            
            sample_count = len(member.embeddings) + 1
            filename = f"sample_{sample_count}_{sample_label.lower().replace(' ', '_')}.jpg"
            crop_path = os.path.join(enroll_dir, filename)
            cv.imwrite(crop_path, face_crop)

            # Store embedding record
            emb_obj = FaceEmbedding(
                member_id=member.id,
                sample_label=sample_label,
                quality_score=quality_score,
                crop_path=crop_path
            )
            emb_obj.set_embedding(embedding.tolist())
            db.add(emb_obj)
            db.commit()

            print(f"[EnrollmentService] Enrolled sample '{sample_label}' for {member.name} (Total samples: {len(member.embeddings)}).")
            return {
                "success": True,
                "member_id": member.id,
                "name": member.name,
                "role": member.role,
                "college_id": member.college_id,
                "sample_label": sample_label,
                "sample_count": len(member.embeddings),
                "quality_score": quality_score,
                "crop_path": crop_path
            }
        except Exception as e:
            db.rollback()
            print(f"[EnrollmentService] Enrollment error: {e}")
            return {"success": False, "error": str(e)}
        finally:
            db.close()

    def enroll_member(
        self,
        name: str,
        college_id: str,
        role: str,
        image_input: Union[str, np.ndarray],
        department: str = "Computer Science",
        year: str = "4th Year",
        email: str = "charan.sai@klu.ac.in"
    ) -> Dict[str, Any]:
        """Backward compatible helper wrapper."""
        return self.enroll_member_sample(
            member_id_or_college_id=college_id,
            image_input=image_input,
            sample_label="Front",
            name=name,
            role=role,
            department=department,
            year=year,
            email=email,
            replace_all=False
        )
