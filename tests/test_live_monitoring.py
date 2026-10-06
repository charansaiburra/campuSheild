import os
import unittest
from unittest.mock import MagicMock, patch

import cv2
import numpy as np

from ai_engine.detection.face_detector import FaceDetector
from ai_engine.detection.person_detector import PersonDetector
from ai_engine.pipeline.video_source import VideoFileSource, WebcamSource
from ai_engine.tracking.tracker import ByteTrackerWrapper


class TestLiveMonitoringFoundation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.video_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "test_datas", "testing_video.mp4"))

    def test_valid_video_source_reads_frame_and_releases(self):
        source = VideoFileSource(self.video_path)
        try:
            self.assertTrue(source.is_opened())
            ok, frame = source.read()
            self.assertTrue(ok)
            self.assertIsNotNone(frame)
            self.assertEqual(len(frame.shape), 3)
        finally:
            source.release()
        self.assertFalse(source.is_opened())

    def test_invalid_video_source_is_reported(self):
        source = VideoFileSource(os.path.join(os.path.dirname(self.video_path), "missing-live-test.mp4"))
        try:
            self.assertFalse(source.is_opened())
            ok, frame = source.read()
            self.assertFalse(ok)
            self.assertIsNone(frame)
            self.assertIn("Unable to open configured video source", source.error)
        finally:
            source.release()

    def test_laptop_camera_index_zero_is_opened_or_reports_actionable_error(self):
        source = WebcamSource(camera_index=0)
        try:
            ok, frame = source.read_frame()
            if ok and frame is not None:
                self.assertTrue(ok)
                self.assertIsNotNone(frame)
            else:
                self.assertFalse(ok)
                self.assertIsNone(frame)
                self.assertIn("Webcam 0 is unavailable or not returning valid frames", source.error)
                self.assertIn("Check Windows camera privacy access", source.error)
                self.assertIn("another application has exclusive access", source.error)
        finally:
            source.release()

    def test_webcam_attempts_fallback_backend_if_preferred_backend_is_unavailable(self):
        failed_backend = MagicMock()
        failed_backend.isOpened.return_value = False
        unavailable_fallback = MagicMock()
        unavailable_fallback.isOpened.return_value = False

        with patch.object(
            WebcamSource,
            "_backends",
            return_value=(("CAP_DSHOW", cv2.CAP_DSHOW), ("CAP_MSMF", cv2.CAP_MSMF)),
        ), patch(
            "ai_engine.pipeline.video_source.cv.VideoCapture",
            side_effect=[failed_backend, unavailable_fallback],
        ) as video_capture:
            source = WebcamSource(camera_index=1)
            try:
                self.assertFalse(source.is_opened())
                self.assertIn("tried CAP_DSHOW, CAP_MSMF", source.error)
                self.assertEqual(video_capture.call_count, 2)
                failed_backend.release.assert_called_once()
                unavailable_fallback.release.assert_called_once()
            finally:
                source.release()

    def test_failed_frame_read_is_thresholded_and_reported(self):
        source = WebcamSource.__new__(WebcamSource)
        source.camera_index = 0
        source.cap = MagicMock()
        source.cap.isOpened.return_value = True
        source.cap.read.return_value = (False, None)
        source.consecutive_read_failures = 0
        source.max_consecutive_read_failures = 3

        ok, frame = source.read_frame()
        self.assertFalse(ok)
        self.assertIsNone(frame)
        self.assertEqual(source.consecutive_read_failures, 1)
        self.assertIn("Webcam 0", source.error)
        self.assertIn("failed to return a valid frame", source.error)
        self.assertIsNotNone(source.cap)

        for _ in range(2):
            source.read_frame()

        self.assertIsNone(source.cap)
        self.assertEqual(source.consecutive_read_failures, 3)

    def test_successful_frame_read_returns_frame(self):
        source = WebcamSource.__new__(WebcamSource)
        source.camera_index = 0
        source.cap = MagicMock()
        source.cap.isOpened.return_value = True
        source.cap.read.return_value = (True, np.zeros((240, 320, 3), dtype=np.uint8))
        source.consecutive_read_failures = 0
        source.error = None

        ok, frame = source.read_frame()
        self.assertTrue(ok)
        self.assertIsNotNone(frame)
        self.assertEqual(frame.shape, (240, 320, 3))
        self.assertEqual(source.consecutive_read_failures, 0)
        self.assertIsNone(source.error)

    def test_pretrained_person_detector_and_bytetrack(self):
        source = VideoFileSource(self.video_path)
        try:
            ok, frame = source.read()
        finally:
            source.release()
        self.assertTrue(ok)
        detector = PersonDetector()
        detected = detector.detect(frame)
        self.assertTrue(detected, "The stored test video should contain at least one detected person")
        self.assertTrue(all(item["class"] == "person" for item in detected))
        self.assertTrue(all(0.0 <= item["confidence"] <= 1.0 for item in detected))

        tracker = ByteTrackerWrapper()
        boxes = [item["bbox"] for item in detected]
        confidences = [item["confidence"] for item in detected]
        _, first_ids = tracker.update_boxes(boxes, confidences)
        _, next_ids = tracker.update_boxes(boxes, confidences)
        self.assertEqual(first_ids, next_ids)
        self.assertTrue(first_ids)

    def test_face_detector_handles_frame_without_faces(self):
        detector = FaceDetector()
        self.assertEqual(detector.detect_faces(np.zeros((240, 320, 3), dtype=np.uint8)), [])


if __name__ == "__main__":
    unittest.main()
