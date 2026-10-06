import os
import sys
import unittest
os.environ["DATABASE_URL"] = "sqlite:///data/live_monitoring_tests.db"
import numpy as np
import cv2 as cv

# Ensure root directory is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from db.database import init_db
from services.enrollment_service import EnrollmentService
from ai_engine.face.face_embedder import FaceEmbedder
from ai_engine.face.face_verifier import FaceVerifier
from ai_engine.detection.face_detector import FaceDetector

class TestFaceVerification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.enrollment_service = EnrollmentService()
        cls.embedder = FaceEmbedder()
        cls.face_detector = FaceDetector()

        # Extract face crop from testing video if available
        video_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "test_datas", "testing_video.mp4"))
        cls.face_crop_a = None

        if os.path.exists(video_path):
            cap = cv.VideoCapture(video_path)
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                boxes = cls.face_detector.detect_faces(frame)
                valid_boxes = [b for b in boxes if (b[2]-b[0]) >= 60 and (b[3]-b[1]) >= 60]
                if valid_boxes:
                    x1, y1, x2, y2 = valid_boxes[0]
                    cls.face_crop_a = frame[y1:y2, x1:x2].copy()
                    break
            cap.release()

        if cls.face_crop_a is None or cls.face_crop_a.size == 0:
            cls.face_crop_a = np.ones((160, 160, 3), dtype=np.uint8) * 180

        # Enroll test member Charan Sai using face_crop_a
        enroll_res = cls.enrollment_service.enroll_member_sample(
            member_id_or_college_id="TEST-CS-001",
            image_input=cls.face_crop_a,
            sample_label="Front",
            name="Charan Sai",
            role="Student",
            department="Computer Science"
        )
        assert enroll_res["success"] is True, f"Enrollment failed: {enroll_res.get('error')}"

        cls.verifier = FaceVerifier()

    def test_a_charan_sai_verified(self):
        """Test A: Enrolled face matching Charan Sai returns status VERIFIED"""
        embedding = self.embedder.generate_embedding(self.face_crop_a)
        self.assertIsNotNone(embedding)
        result = self.verifier.verify_embedding(embedding)
        self.assertEqual(result["status"], "VERIFIED")
        self.assertEqual(result["name"], "Charan Sai")
        self.assertEqual(result["role"], "Student")
        self.assertGreaterEqual(result["similarity"], 0.60)

    def test_b_unknown_face_handling(self):
        """Test B: Non-enrolled/different face returns UNKNOWN/UNVERIFIED"""
        different_face = np.zeros_like(self.face_crop_a)
        embedding = self.embedder.generate_embedding(different_face)
        if embedding is not None:
            result = self.verifier.verify_embedding(embedding)
            self.assertIn(result["status"], ["UNKNOWN", "UNVERIFIED"])
            if result["status"] == "UNKNOWN":
                self.assertIsNone(result["name"])

    def test_c_empty_or_no_face_handling(self):
        """Test C: Empty image or None returns UNKNOWN result without exception"""
        result = self.verifier.verify_embedding(None)
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertIsNone(result["name"])

    def test_d_multi_sample_enrollment(self):
        """Test D: Enroll multiple face samples for same member across viewing angles"""
        res_left = self.enrollment_service.enroll_member_sample(
            member_id_or_college_id="TEST-CS-001",
            image_input=self.face_crop_a,
            sample_label="Slight Left"
        )
        self.assertTrue(res_left["success"])

        res_right = self.enrollment_service.enroll_member_sample(
            member_id_or_college_id="TEST-CS-001",
            image_input=self.face_crop_a,
            sample_label="Slight Right"
        )
        self.assertTrue(res_right["success"])
        self.assertGreaterEqual(res_right["sample_count"], 2)

    def test_e_quality_validation_rejection(self):
        """Test E: Reject small face or invalid image with appropriate error message"""
        small_face = np.ones((20, 20, 3), dtype=np.uint8) * 100
        res = self.enrollment_service.enroll_member_sample(
            member_id_or_college_id="TEST-CS-001",
            image_input=small_face,
            sample_label="Front"
        )
        self.assertFalse(res["success"])
        self.assertIn("Face is too small", res["error"])

if __name__ == "__main__":
    unittest.main()
