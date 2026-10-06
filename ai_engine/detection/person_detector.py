import os
import cv2 as cv
import numpy as np
from typing import List, Dict, Any
from ultralytics import YOLO

class PersonDetector:
    _instance = None

    def __new__(cls, model_path: str = None):
        if cls._instance is None:
            cls._instance = super(PersonDetector, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, model_path: str = None):
        if self._initialized:
            return
        # Keep body detection separate from the face-specific identity model.
        # Ultralytics downloads its official pretrained COCO weights on demand.
        model_path = model_path or os.getenv("PERSON_DETECTOR_MODEL_PATH", "yolo_models/yolov8n.pt")
        self.model = YOLO(model_path)
        names = self.model.names
        name_items = names.items() if isinstance(names, dict) else enumerate(names)
        if not any(str(name).lower() == "person" for _, name in name_items):
            raise ValueError(f"Configured person detector has no person class: {model_path}")
        self._initialized = True

    def detect(self, frame: np.ndarray, conf_threshold: float = 0.40) -> List[tuple]:
        """
        Runs object detection on frame and returns raw Ultralytics results object safely.
        """
        if frame is None or frame.size == 0:
            return []
        try:
            results = self.model(frame, verbose=False)[0]
            if results.boxes is None:
                return []
            names = self.model.names
            name_items = names.items() if isinstance(names, dict) else enumerate(names)
            person_class = next(class_id for class_id, name in name_items if str(name).lower() == "person")
            boxes = []
            for detection in results.boxes:
                if int(detection.cls[0].item()) != person_class or float(detection.conf[0].item()) < conf_threshold:
                    continue
                x1, y1, x2, y2 = detection.xyxy[0].cpu().numpy().astype(int).tolist()
                boxes.append({
                    "bbox": (x1, y1, x2, y2),
                    "confidence": float(detection.conf[0].item()),
                    "class": "person",
                })
            return boxes
        except Exception as e:
            raise RuntimeError(f"Person detection failed: {e}") from e
