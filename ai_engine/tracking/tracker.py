import supervision as sv
import numpy as np
from typing import List, Tuple, Optional


class ByteTrackerWrapper:
    def __init__(self, track_activation_threshold: float = 0.25, lost_track_buffer: int = 30):
        self.tracker = sv.ByteTrack(
            track_activation_threshold=track_activation_threshold,
            lost_track_buffer=lost_track_buffer,
        )

    @staticmethod
    def _ids(detections: sv.Detections) -> List[Optional[int]]:
        track_ids = detections.tracker_id
        if track_ids is None:
            return [None] * len(detections)
        return [None if track_id is None else int(track_id) for track_id in track_ids]

    def update(self, ultralytics_results) -> Tuple[sv.Detections, List[int]]:
        """Update ByteTrack from an Ultralytics result object."""
        if ultralytics_results is None or len(ultralytics_results) == 0:
            return self.tracker.update_with_detections(sv.Detections.empty()), []
        try:
            detections = sv.Detections.from_ultralytics(ultralytics_results)
            tracked = self.tracker.update_with_detections(detections)
            return tracked, self._ids(tracked)
        except Exception as exc:
            print(f"[ByteTrackerWrapper] Tracking update error: {exc}")
            return sv.Detections.empty(), []

    def update_boxes(self, boxes: List[Tuple[int, int, int, int]], confidences=None) -> Tuple[sv.Detections, List[int]]:
        """Track detector boxes when the active detector exposes boxes directly."""
        try:
            xyxy = np.asarray(boxes, dtype=np.float32).reshape((-1, 4))
            if not len(xyxy):
                tracked = self.tracker.update_with_detections(sv.Detections.empty())
                return tracked, []
            detections = sv.Detections(
                xyxy=xyxy,
                confidence=np.asarray(confidences, dtype=np.float32) if confidences is not None else np.ones(len(xyxy), dtype=np.float32),
                class_id=np.zeros(len(xyxy), dtype=int),
            )
            tracked = self.tracker.update_with_detections(detections)
            return tracked, self._ids(tracked)
        except Exception as exc:
            print(f"[ByteTrackerWrapper] Box tracking error: {exc}")
            return sv.Detections.empty(), []
