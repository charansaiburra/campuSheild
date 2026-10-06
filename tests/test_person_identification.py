import unittest
import os
import secrets
import sys
import numpy as np
import cv2 as cv
from datetime import datetime, timezone
os.environ["DATABASE_URL"] = "sqlite:///data/live_monitoring_tests.db"
os.environ["JWT_SECRET"] = secrets.token_urlsafe(48)
os.environ["CAMPUSHIELD_BOOTSTRAP_ADMIN_EMAIL"] = "admin@klu.ac.in"
os.environ["CAMPUSHIELD_BOOTSTRAP_ADMIN_PASSWORD"] = secrets.token_urlsafe(32)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from fastapi.testclient import TestClient
from backend.app.main import app
from db.database import SessionLocal, init_db
from db.models import CollegeMember, User
from services.auth_service import hash_password
from services.enrollment_service import EnrollmentService
from scripts.seed_initial_data import seed_data
from backend.app.api.v1.identification import _utc_timestamp_iso

class TestPersonIdentification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        seed_data()
        cls.admin_password = os.environ["CAMPUSHIELD_BOOTSTRAP_ADMIN_PASSWORD"]
        db = SessionLocal()
        try:
            admin = db.query(User).filter(User.role == "ADMIN").first()
            if admin is None:
                admin = User(username="admin", email="admin@klu.ac.in", hashed_password=hash_password(cls.admin_password), role="ADMIN")
                db.add(admin)
            else:
                admin.email = "admin@klu.ac.in"
                admin.hashed_password = hash_password(cls.admin_password)
                admin.is_active = True
            db.commit()
        finally:
            db.close()
        cls.client = TestClient(app)
        login = cls.client.post("/api/v1/auth/login", json={
            "email": "admin@klu.ac.in", "password": cls.admin_password
        })
        if login.status_code != 200:
            raise AssertionError(f"Seeded Admin login failed: {login.status_code} {login.text}")
        cls.client.headers.update({"Authorization": f"Bearer {login.json()['access_token']}"})
        cls.enrollment_service = EnrollmentService()

        # Create synthetic face image (120x120)
        img = np.ones((120, 120, 3), dtype=np.uint8) * 180
        cv.circle(img, (60, 60), 35, (120, 120, 120), -1)
        cv.circle(img, (48, 50), 5, (0, 0, 0), -1)
        cv.circle(img, (72, 50), 5, (0, 0, 0), -1)
        cv.ellipse(img, (60, 75), (15, 8), 0, 0, 180, (0, 0, 0), 2)
        cls.face_crop = img

    def test_a_identify_enrolled_person(self):
        """Test identification of enrolled person Charan Sai"""
        success, img_bytes = cv.imencode('.jpg', self.face_crop)
        self.assertTrue(success)

        response = self.client.post(
            "/api/v1/person-identification",
            files={"file": ("test_face.jpg", img_bytes.tobytes(), "image/jpeg")}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn(data["status"], ["VERIFIED", "UNKNOWN"])
        if data["status"] == "VERIFIED":
            self.assertEqual(data["member"]["name"], "Charan Sai")
            self.assertIn("similarity", data)

    def test_b_identify_no_face(self):
        """Test identification when image contains no face"""
        blank_img = np.zeros((300, 300, 3), dtype=np.uint8)
        success, img_bytes = cv.imencode('.jpg', blank_img)
        self.assertTrue(success)

        response = self.client.post(
            "/api/v1/person-identification",
            files={"file": ("blank.jpg", img_bytes.tobytes(), "image/jpeg")}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertEqual(data["status"], "NO_FACE")
        self.assertIn("No face detected", data["message"])

    def test_c_identification_history(self):
        """Test fetching identification history audit log"""
        response = self.client.get("/api/v1/person-identification/history")
        self.assertEqual(response.status_code, 200)
        history = response.json()
        self.assertIsInstance(history, list)

    def test_d_identification_logs_include_utc_timezone(self):
        encoded, img_bytes = cv.imencode('.jpg', self.face_crop)
        self.assertTrue(encoded)
        before = self.client.get("/api/v1/person-identification/history").json()
        before_ids = {item["id"] for item in before}
        request_windows = []
        for _ in range(2):
            request_started = datetime.now(timezone.utc)
            response = self.client.post(
                "/api/v1/person-identification",
                files={"file": ("test_face.jpg", img_bytes.tobytes(), "image/jpeg")}
            )
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["success"])
            request_windows.append((request_started, datetime.now(timezone.utc)))

        history = self.client.get("/api/v1/person-identification/history").json()
        new_logs = [item for item in history if item["id"] not in before_ids]
        self.assertGreaterEqual(len(new_logs), 2)
        parsed_logs = []
        for item, (request_started, request_finished) in zip(new_logs[:2][::-1], request_windows):
            self.assertTrue(item["timestamp"].endswith("Z"), item["timestamp"])
            parsed = datetime.fromisoformat(item["timestamp"].replace("Z", "+00:00"))
            self.assertEqual(parsed.utcoffset().total_seconds(), 0)
            self.assertGreaterEqual(parsed, request_started)
            self.assertLessEqual(parsed, request_finished)
            parsed_logs.append(parsed)
        self.assertGreater(parsed_logs[1], parsed_logs[0])

        legacy_naive_utc = datetime(2025, 1, 2, 10, 30)
        self.assertEqual(_utc_timestamp_iso(legacy_naive_utc), "2025-01-02T10:30:00Z")

if __name__ == "__main__":
    unittest.main()
