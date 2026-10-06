import os
import cv2 as cv
import numpy as np
from typing import List, Tuple
from ultralytics import YOLO

class FaceDetector:
    _instance = None

    def __new__(cls, model_path: str = "yolo_models/yolov8n-face.pt"):
        if cls._instance is None:
            cls._instance = super(FaceDetector, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, model_path: str = "yolo_models/yolov8n-face.pt"):
        if self._initialized:
            return
        model_path = os.getenv("FACE_DETECTOR_MODEL_PATH", model_path)
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"YOLO face model weight file not found at: {model_path}")
        self.model = YOLO(model_path)
        self._initialized = True

    def detect_faces(self, frame: np.ndarray, conf_threshold: float = 0.40) -> List[Tuple[int, int, int, int]]:
        """
        Detects faces in BGR frame and returns validated integer bounding box coordinates [x1, y1, x2, y2].
        Guarantees bounding boxes remain within valid frame dimensions.
        """
        if frame is None or frame.size == 0:
            return []

        h, w, _ = frame.shape
        boxes = []

        try:
            results = self.model(frame, verbose=False)[0]
            if results.boxes is None or len(results.boxes) == 0:
                return []

            for box in results.boxes:
                conf = float(box.conf[0].cpu().numpy()) if box.conf is not None else 0.0
                if conf < conf_threshold:
                    continue

                xyxy = box.xyxy[0].cpu().numpy()
                x1, y1, x2, y2 = map(int, xyxy[:4])

                # Clamp bounding boxes strictly inside image boundaries
                x1 = max(0, min(x1, w - 1))
                y1 = max(0, min(y1, h - 1))
                x2 = max(0, min(x2, w))
                y2 = max(0, min(y2, h))

                if x2 - x1 >= 10 and y2 - y1 >= 10:
                    boxes.append((x1, y1, x2, y2))
        except Exception as e:
            raise RuntimeError(f"Face detection failed: {e}") from e

        return boxes
