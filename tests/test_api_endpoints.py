import os
import secrets
import sys
import unittest
from fastapi.testclient import TestClient

# Keep API tests away from the project's enrolled-member database.
os.environ["DATABASE_URL"] = "sqlite:///data/live_monitoring_tests.db"
os.environ["JWT_SECRET"] = secrets.token_urlsafe(48)
os.environ["CAMPUSHIELD_BOOTSTRAP_ADMIN_EMAIL"] = "admin@klu.ac.in"
os.environ["CAMPUSHIELD_BOOTSTRAP_ADMIN_PASSWORD"] = secrets.token_urlsafe(32)
os.environ["CAMPUSHIELD_BOOTSTRAP_SECURITY_OFFICER_EMAIL"] = "officer@klu.ac.in"
os.environ["CAMPUSHIELD_BOOTSTRAP_SECURITY_OFFICER_PASSWORD"] = secrets.token_urlsafe(32)

# Ensure root directory is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.main import app
from backend.app.api.v1.monitoring import active_camera_streams
from scripts.seed_initial_data import seed_data
from db.database import SessionLocal
from db.models import User
from services.auth_service import hash_password, decode_jwt_token

class TestApiEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed_data()
        cls.admin_password = os.environ["CAMPUSHIELD_BOOTSTRAP_ADMIN_PASSWORD"]
        cls.officer_password = os.environ["CAMPUSHIELD_BOOTSTRAP_SECURITY_OFFICER_PASSWORD"]
        db = SessionLocal()
        try:
            for role, email, password, username in (
                ("ADMIN", "admin@klu.ac.in", cls.admin_password, "admin"),
                ("SECURITY_OFFICER", "officer@klu.ac.in", cls.officer_password, "officer"),
            ):
                user = db.query(User).filter(User.role == role).first()
                if user is None:
                    user = User(username=username, email=email, hashed_password=hash_password(password), role=role)
                    db.add(user)
                else:
                    user.email = email
                    user.hashed_password = hash_password(password)
                    user.is_active = True
            db.commit()
        finally:
            db.close()
        cls.client = TestClient(app)
        login = cls.client.post("/api/v1/auth/login", json={
            "email": "admin@klu.ac.in", "password": cls.admin_password
        })
        if login.status_code != 200:
            raise AssertionError(f"Seeded Admin login failed: {login.status_code} {login.text}")
        cls.token = login.json()["access_token"]
        cls.client.headers.update({"Authorization": f"Bearer {cls.token}"})

    def test_root_endpoint(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["system"], "CampusShield AI Security Platform")

    def test_login_success(self):
        res = self.client.post("/api/v1/auth/login", json={
            "email": "ADMIN@KLU.AC.IN",
            "password": self.admin_password
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["user"]["role"], "ADMIN")

    def test_invalid_login_rejected(self):
        bad_password = self.client.post("/api/v1/auth/login", json={
            "email": "admin@klu.ac.in", "password": secrets.token_urlsafe(32)
        })
        bad_user = self.client.post("/api/v1/auth/login", json={
            "email": "missing@klu.ac.in", "password": self.admin_password
        })
        invalid_domain = self.client.post("/api/v1/auth/login", json={
            "email": "admin@example.org", "password": self.admin_password
        })
        missing_field = self.client.post("/api/v1/auth/login", json={"email": "admin@klu.ac.in"})
        self.assertEqual(bad_password.status_code, 401)
        self.assertEqual(bad_user.status_code, 401)
        self.assertEqual(invalid_domain.status_code, 422)
        self.assertEqual(missing_field.status_code, 422)

    def test_officer_login_jwt_and_role_based_access(self):
        response = self.client.post("/api/v1/auth/login", json={
            "email": "officer@klu.ac.in", "password": self.officer_password
        })
        self.assertEqual(response.status_code, 200)
        token = response.json()["access_token"]
        self.assertEqual(decode_jwt_token(token)["role"], "SECURITY_OFFICER")
        self.assertEqual(response.json()["user"]["email"], "officer@klu.ac.in")
        denied = self.client.post("/api/v1/cameras", headers={"Authorization": f"Bearer {token}"}, json={
            "name": "RBAC check", "location": "Test", "source_type": "WEBCAM", "source_url": "0"
        })
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(self.client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code, 200)

    def test_protected_api_rejects_invalid_token(self):
        response = self.client.get("/api/v1/dashboard/summary", headers={"Authorization": "Bearer invalid"})
        self.assertEqual(response.status_code, 401)

    def test_protected_api_rejects_missing_token(self):
        response = TestClient(app).get("/api/v1/dashboard/summary")
        self.assertEqual(response.status_code, 401)

    def test_dashboard_summary(self):
        res = self.client.get("/api/v1/dashboard/summary")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("cards", data)
        self.assertGreaterEqual(data["cards"]["total_cameras"], 1)

    def test_camera_crud(self):
        # Create camera
        res = self.client.post("/api/v1/cameras", json={
            "name": "Test CCTV Camera",
            "location": "North Building",
            "source_type": "WEBCAM",
            "source_url": "0"
        })
        self.assertEqual(res.status_code, 200)
        cam_id = res.json()["id"]

        # List cameras
        res_list = self.client.get("/api/v1/cameras")
        self.assertEqual(res_list.status_code, 200)
        self.assertTrue(any(c["id"] == cam_id for c in res_list.json()))

        # Delete camera
        res_del = self.client.delete(f"/api/v1/cameras/{cam_id}")
        self.assertEqual(res_del.status_code, 200)

    def test_member_crud(self):
        res = self.client.get("/api/v1/members")
        self.assertEqual(res.status_code, 200)
        members = res.json()
        self.assertTrue(any(m["name"] == "Charan Sai" for m in members))

    def test_restricted_zones(self):
        res = self.client.get("/api/v1/zones")
        self.assertEqual(res.status_code, 200)

    def test_monitoring_websocket_streams_real_video(self):
        cameras = self.client.get("/api/v1/cameras").json()
        camera = next((camera for camera in cameras if camera["source_type"] == "VIDEO_FILE"), None)
        self.assertIsNotNone(camera, "Seeder should provide a recorded video source")
        with self.client.websocket_connect(
            f"/api/v1/monitoring/ws/{camera['id']}",
            subprotocols=["campus-security", f"bearer.{self.token}"],
        ) as websocket:
            payload = websocket.receive_json()
            self.assertEqual(payload["type"], "telemetry")
            telemetry = payload["data"]
            self.assertTrue(telemetry["frame"].startswith("data:image/jpeg;base64,"))
            self.assertEqual(telemetry["source_status"], "LIVE")
            self.assertIn("person_detection_available", telemetry["summary"])
            self.assertTrue(telemetry["summary"]["person_detection_available"])
            self.assertGreaterEqual(telemetry["person_count"], 0)
            for detection in telemetry["detections"]:
                self.assertIsInstance(detection["track_id"], int)
                self.assertEqual(len(detection["bbox"]), 4)
            websocket.send_json({"type": "stop"})
            self.assertEqual(websocket.receive_json()["type"], "stopped")
        self.assertNotIn(camera["id"], active_camera_streams)

        with self.client.websocket_connect(
            f"/api/v1/monitoring/ws/{camera['id']}",
            subprotocols=["campus-security", f"bearer.{self.token}"],
        ) as websocket:
            self.assertEqual(websocket.receive_json()["type"], "telemetry")
            websocket.send_json({"type": "stop"})
            self.assertEqual(websocket.receive_json()["type"], "stopped")
        self.assertNotIn(camera["id"], active_camera_streams)

    def test_monitoring_rejects_invalid_and_unavailable_sources(self):
        with self.client.websocket_connect(
            "/api/v1/monitoring/ws/not-a-camera",
            subprotocols=["campus-security", f"bearer.{self.token}"],
        ) as missing:
            self.assertEqual(missing.receive_json()["code"], "CAMERA_NOT_FOUND")

        created = self.client.post("/api/v1/cameras", json={
            "name": "Unavailable source check",
            "location": "Test",
            "source_type": "VIDEO_FILE",
            "source_url": "data/missing-verification-video.mp4",
        })
        self.assertEqual(created.status_code, 200)
        camera_id = created.json()["id"]
        try:
            with self.client.websocket_connect(
                f"/api/v1/monitoring/ws/{camera_id}",
                subprotocols=["campus-security", f"bearer.{self.token}"],
            ) as unavailable:
                self.assertEqual(unavailable.receive_json()["code"], "CAMERA_SOURCE_UNAVAILABLE")
        finally:
            self.client.delete(f"/api/v1/cameras/{camera_id}")

    def test_events_and_alerts(self):
        res_events = self.client.get("/api/v1/events")
        self.assertEqual(res_events.status_code, 200)

        res_alerts = self.client.get("/api/v1/alerts")
        self.assertEqual(res_alerts.status_code, 200)

if __name__ == "__main__":
    unittest.main()
