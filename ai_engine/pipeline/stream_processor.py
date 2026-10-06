import os
import time
import cv2 as cv
import numpy as np
from typing import Dict, Any, Tuple, List

from ai_engine.detection.face_detector import FaceDetector
from ai_engine.detection.person_detector import PersonDetector
from ai_engine.tracking.tracker import ByteTrackerWrapper
from ai_engine.face.face_embedder import FaceEmbedder
from ai_engine.face.face_verifier import FaceVerifier

class StreamProcessor:
    def __init__(self, cache_ttl_seconds: float = 3.0):
        self.face_detector = FaceDetector()
        self.tracker = ByteTrackerWrapper()
        self.person_tracker = ByteTrackerWrapper()
        self.person_detector = None
        self.person_detection_error = None
        try:
            self.person_detector = PersonDetector()
        except Exception as exc:
            self.person_detection_error = str(exc)
            print(f"[StreamProcessor] Person detection unavailable: {exc}")
        self.embedder = FaceEmbedder()
        self.verifier = FaceVerifier()

        # Recognition Cache: track_id -> {"result": dict, "last_updated": float}
        self.recognition_cache: Dict[int, Dict[str, Any]] = {}
        self.cache_ttl = cache_ttl_seconds

        # FPS calculation
        self.prev_time = time.time()
        self.fps = 0.0
        self.frame_number = 0
        self.max_processing_fps = max(0.1, float(os.getenv("MAX_PROCESSING_FPS", "8")))

    def process_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, List[Dict[str, Any]], Dict[str, int]]:
        """
        Processes a single video frame:
        1. Detects faces
        2. Updates ByteTrack tracking IDs
        3. Generates embeddings & verifies identities (with caching per track_id)
        4. Draws CCTV UI overlay
        Returns (annotated_frame, active_detections_list, summary_counts)
        """
        if frame is None or frame.size == 0:
            return frame, [], {"total": 0, "verified": 0, "unverified": 0, "persons": 0, "person_detection_available": self.person_detector is not None}
        if self.person_detector is None:
            raise RuntimeError(f"Person detection model is unavailable: {self.person_detection_error or 'no configured detector'}")

        annotated_frame = frame.copy()
        h, w, _ = frame.shape
        self.frame_number += 1

        # Calculate FPS
        curr_time = time.time()
        delta = curr_time - self.prev_time
        if delta > 0:
            self.fps = 0.9 * self.fps + 0.1 * (1.0 / delta)
        self.prev_time = curr_time

        # 1. Detect faces
        face_boxes = self.face_detector.detect_faces(frame)

        # 2. Detect and track full person boxes separately from face identity.
        person_detections = self.person_detector.detect(frame)
        if person_detections is None:
            raise RuntimeError("Person detection returned no result; refusing to substitute face counts for person detections")
        person_boxes = [detection["bbox"] for detection in person_detections]
        person_confidences = [detection["confidence"] for detection in person_detections]
        person_tracks, person_track_ids = self.person_tracker.update_boxes(person_boxes, person_confidences)
        tracked, face_track_ids = self.tracker.update_boxes(face_boxes)
        tracked_boxes = tracked.xyxy if len(tracked) else np.empty((0, 4))
        person_tracked_boxes = person_tracks.xyxy if person_tracks is not None and len(person_tracks) else np.empty((0, 4))

        def matched_id(box, boxes, ids):
            if not len(boxes) or not ids:
                return None
            center = np.array([(box[0] + box[2]) / 2, (box[1] + box[3]) / 2])
            centers = (boxes[:, :2] + boxes[:, 2:]) / 2
            nearest = int(np.argmin(np.linalg.norm(centers - center, axis=1)))
            if nearest < len(ids) and np.linalg.norm(centers[nearest] - center) < max(w, h) * 0.2:
                return ids[nearest]
            return None

        face_ids = [matched_id(box, tracked_boxes, face_track_ids) for box in face_boxes]
        person_ids = [matched_id(box, person_tracked_boxes, person_track_ids) for box in person_boxes]
        active_track_results = []
        verified_count = 0
        unverified_count = 0

        if face_boxes:
            # Format detections for ByteTrack update
            boxes_array = np.array(face_boxes, dtype=np.float32)
            # Create synthetic ultralytics result object format or manual track mapping
            for idx, box in enumerate(face_boxes):
                x1, y1, x2, y2 = box
                track_id = face_ids[idx]
                person_box = box
                person_track_id = None
                person_confidence = 0.0
                if self.person_detector:
                    face_center = ((x1 + x2) / 2, (y1 + y2) / 2)
                    for person_index, candidate in enumerate(person_boxes):
                        if candidate[0] <= face_center[0] <= candidate[2] and candidate[1] <= face_center[1] <= candidate[3]:
                            person_box = candidate
                            person_track_id = person_ids[person_index]
                            person_confidence = person_confidences[person_index]
                            break
                    if person_track_id is not None:
                        track_id = person_track_id

                # Extract face region
                face_crop = frame[y1:y2, x1:x2]

                # Check cache for track_id
                now = time.time()
                cached = self.recognition_cache.get(track_id) if track_id is not None else None

                if cached and (now - cached["last_updated"]) < self.cache_ttl:
                    rec_result = cached["result"]
                else:
                    # Generate FaceNet embedding & verify
                    embedding = self.embedder.generate_embedding(face_crop)
                    if embedding is None:
                        raise RuntimeError("Face embedding generation failed; refusing to report an unknown identity")
                    rec_result = self.verifier.verify_embedding(embedding)
                    if track_id is not None:
                        self.recognition_cache[track_id] = {
                            "result": rec_result,
                            "last_updated": now
                        }

                status = "VERIFIED" if rec_result.get("status") == "VERIFIED" else "UNKNOWN"
                name = rec_result.get("name") or "UNKNOWN"
                role = rec_result.get("role") or "UNVERIFIED"

                if status == "VERIFIED":
                    verified_count += 1
                    box_color = (0, 255, 0)      # Green
                else:
                    unverified_count += 1
                    box_color = (0, 165, 255)    # Orange/Amber

                # 3. Annotate frame
                # Draw bounding box
                cv.rectangle(annotated_frame, (person_box[0], person_box[1]), (person_box[2], person_box[3]), box_color, 2)
                cv.rectangle(annotated_frame, (x1, y1), (x2, y2), (255, 200, 0), 1)

                # Draw label background header
                header_text = f"#{track_id} {name}" if track_id is not None else name
                sub_text = f"{status} | {role}"

                font = cv.FONT_HERSHEY_SIMPLEX
                font_scale = 0.5
                thickness = 1

                (tw1, th1), _ = cv.getTextSize(header_text, font, font_scale, thickness)
                (tw2, th2), _ = cv.getTextSize(sub_text, font, font_scale - 0.1, thickness)

                banner_width = max(tw1, tw2) + 10
                banner_height = th1 + th2 + 12

                # Banner background rectangle
                bg_y1 = max(0, y1 - banner_height)
                bg_y2 = bg_y1 + banner_height
                cv.rectangle(annotated_frame, (x1, bg_y1), (x1 + banner_width, bg_y2), box_color, -1)

                # Banner text (white on box_color)
                text_color = (255, 255, 255)
                cv.putText(annotated_frame, header_text, (x1 + 5, bg_y1 + th1 + 2), font, font_scale, text_color, thickness, cv.LINE_AA)
                cv.putText(annotated_frame, sub_text, (x1 + 5, bg_y1 + th1 + th2 + 6), font, font_scale - 0.1, text_color, thickness, cv.LINE_AA)

                active_track_results.append({
                    "track_id": track_id,
                    "bbox": list(person_box),
                    "face_bbox": [x1, y1, x2, y2],
                    "confidence": person_confidence,
                    "class": "person",
                    "status": status,
                    "face_status": status,
                    "name": name,
                    "role": role,
                    "member_id": rec_result.get("member_id"),
                    "college_id": rec_result.get("college_id"),
                    "department": rec_result.get("department"),
                    "similarity": rec_result.get("similarity", 0.0)
                })

        # Keep detected people visible even when no face is available for identity.
        if self.person_detector:
            for index, person_box in enumerate(person_boxes):
                if any(person_box[0] <= (face[0] + face[2]) / 2 <= person_box[2] and person_box[1] <= (face[1] + face[3]) / 2 <= person_box[3] for face in face_boxes):
                    continue
                track_id = person_ids[index]
                cv.rectangle(annotated_frame, (person_box[0], person_box[1]), (person_box[2], person_box[3]), (180, 180, 180), 2)
                label = f"#{track_id} NO FACE" if track_id is not None else "NO FACE / NO TRACK"
                cv.putText(annotated_frame, label, (person_box[0], max(18, person_box[1] - 6)), cv.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1, cv.LINE_AA)
                active_track_results.append({"track_id": track_id, "bbox": list(person_box), "confidence": person_confidences[index], "class": "person", "status": "NO FACE", "face_status": "NO FACE", "name": "UNKNOWN", "role": "UNVERIFIED", "similarity": 0.0})

        # 4. Top Status Header Overlay
        unverified_count = max(0, len(person_boxes) - verified_count)
        overlay_text = f"LIVE MONITORING | FPS: {self.fps:.1f} | People: {len(person_boxes)} | Verified: {verified_count} | Unverified: {unverified_count}"
        cv.rectangle(annotated_frame, (0, 0), (w, 35), (20, 20, 20), -1)
        cv.putText(annotated_frame, overlay_text, (10, 23), cv.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1, cv.LINE_AA)

        summary = {
            "total": len(person_boxes),
            "verified": verified_count,
            "unverified": unverified_count,
            "persons": len(person_boxes),
            "person_detection_available": True,
            "person_detection_error": self.person_detection_error,
        }

        return annotated_frame, active_track_results, summary
