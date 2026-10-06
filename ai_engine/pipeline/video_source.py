import logging
import os
import time
import cv2 as cv
import numpy as np
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class CameraSourceError(RuntimeError):
    """A configured camera could not be opened or stopped returning valid frames."""


class VideoSource:
    def __init__(self):
        self.error = None
        self.end_of_stream = False
        self.consecutive_read_failures = 0
        self.max_consecutive_read_failures = 3

    def open(self):
        raise NotImplementedError

    def is_opened(self) -> bool:
        return bool(getattr(self, "cap", None) and self.cap.isOpened())

    def read(self):
        return self.read_frame()

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        raise NotImplementedError

    def release(self):
        pass


class WebcamSource(VideoSource):
    def __init__(self, camera_index: int = 0):
        super().__init__()
        self.camera_index = camera_index
        self.cap = None
        self.backend_name = None
        self._pending_frame = None
        self.open()

    @staticmethod
    def _is_valid_frame(frame) -> bool:
        return (
            isinstance(frame, np.ndarray)
            and frame.ndim == 3
            and frame.shape[0] > 0
            and frame.shape[1] > 0
            and frame.shape[2] in (1, 3, 4)
            and frame.size > 0
            and frame.dtype.kind in "uif"
        )

    @staticmethod
    def _backends():
        if os.name == "nt":
            return (
                ("CAP_DSHOW", cv.CAP_DSHOW),
                ("CAP_MSMF", cv.CAP_MSMF),
                ("CAP_ANY", cv.CAP_ANY),
            )
        return (("CAP_ANY", cv.CAP_ANY),)

    def open(self) -> bool:
        self.release()
        self.consecutive_read_failures = 0
        attempted_backends = []

        for backend_name, backend in self._backends():
            attempted_backends.append(backend_name)
            cap = None
            try:
                logger.info(
                    "[Camera] Opening webcam index %s with %s",
                    self.camera_index,
                    backend_name,
                )
                cap = cv.VideoCapture(self.camera_index, backend)
                if not cap.isOpened():
                    logger.warning(
                        "[Camera] Webcam index %s did not open with %s",
                        self.camera_index,
                        backend_name,
                    )
                    continue

                for read_attempt in range(1, 4):
                    ok, frame = cap.read()
                    if ok and self._is_valid_frame(frame):
                        self.cap = cap
                        self.backend_name = backend_name
                        self._pending_frame = frame
                        self.error = None
                        logger.info(
                            "[Camera] Webcam index %s opened with %s; first frame is %sx%s",
                            self.camera_index,
                            backend_name,
                            frame.shape[1],
                            frame.shape[0],
                        )
                        return True

                    logger.warning(
                        "[Camera] Webcam index %s read failed with %s "
                        "(attempt %s/3; frame shape=%s)",
                        self.camera_index,
                        backend_name,
                        read_attempt,
                        getattr(frame, "shape", None),
                    )
                    if read_attempt < 3:
                        time.sleep(0.1)
            except Exception:
                logger.exception(
                    "[Camera] OpenCV failed for webcam index %s with %s",
                    self.camera_index,
                    backend_name,
                )
            finally:
                if cap is not None and cap is not self.cap:
                    cap.release()

        self.error = (
            f"Webcam {self.camera_index} is unavailable or not returning valid frames "
            f"(tried {', '.join(attempted_backends)}). Check Windows camera privacy access "
            "and whether another application has exclusive access."
        )
        logger.error("[Camera] %s", self.error)
        return False

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        if not self.cap or not self.cap.isOpened():
            self.consecutive_read_failures += 1
            if not self.error:
                self.error = f"Webcam {self.camera_index} is not open; retry the camera connection."
            return False, None

        pending_frame = getattr(self, "_pending_frame", None)
        if pending_frame is not None:
            frame = pending_frame
            self._pending_frame = None
            self.consecutive_read_failures = 0
            self.error = None
            return True, frame

        try:
            ret, frame = self.cap.read()
        except cv.error:
            logger.exception(
                "[Camera] OpenCV read raised an error for webcam index %s using %s",
                self.camera_index,
                getattr(self, "backend_name", None) or "unknown backend",
            )
            ret, frame = False, None
        if not ret or not self._is_valid_frame(frame):
            self.consecutive_read_failures += 1
            self.error = (
                f"Webcam {self.camera_index} ({getattr(self, 'backend_name', None) or 'unknown backend'}) "
                "failed to return a valid frame. Check Windows camera privacy access "
                "and whether another application has exclusive access."
            )
            logger.warning(
                "[Camera] Webcam index %s frame read failed (%s/%s; shape=%s)",
                self.camera_index,
                self.consecutive_read_failures,
                self.max_consecutive_read_failures,
                getattr(frame, "shape", None),
            )
            if self.consecutive_read_failures >= self.max_consecutive_read_failures:
                logger.error(
                    "[Camera] Releasing failed webcam index %s capture from %s",
                    self.camera_index,
                    getattr(self, "backend_name", None) or "unknown backend",
                )
                self.release()
            return False, None

        self.consecutive_read_failures = 0
        self.error = None
        logger.debug(
            "[Camera] Webcam index %s read frame %sx%s using %s",
            self.camera_index,
            frame.shape[1],
            frame.shape[0],
            getattr(self, "backend_name", None),
        )
        return ret, frame

    def release(self):
        cap, self.cap = self.cap, None
        self._pending_frame = None
        self.backend_name = None
        if cap is not None:
            cap.release()


class VideoFileSource(VideoSource):
    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path
        self.cap = None
        self.open()

    def open(self) -> bool:
        if self.cap:
            self.cap.release()
        self.cap = cv.VideoCapture(self.file_path)
        if not self.cap.isOpened():
            self.error = f"Unable to open configured video source: {self.file_path}"
        else:
            self.error = None
            self.end_of_stream = False
        return self.cap.isOpened()

    def read_frame(self) -> Tuple[bool, Optional[cv.Mat]]:
        if not self.cap or not self.cap.isOpened():
            if not self.error:
                self.error = f"Video source is unavailable: {self.file_path}"
            return False, None
        ret, frame = self.cap.read()
        if not ret or frame is None:
            self.end_of_stream = True
            self.error = f"End of video source: {self.file_path}"
        return ret, frame

    def release(self):
        if self.cap:
            self.cap.release()
            self.cap = None


def validate_source_config(source_type: str, source_url: str) -> None:
    if source_type not in {"WEBCAM", "VIDEO_FILE", "RTSP"}:
        raise ValueError("Source type must be WEBCAM, VIDEO_FILE, or RTSP")
    value = (source_url or "").strip()
    if not value:
        raise ValueError("Camera source URL or index is required")
    if source_type == "WEBCAM" and not value.isdecimal():
        raise ValueError("Webcam source must be a non-negative device index")
    if source_type == "RTSP" and not value.lower().startswith(("rtsp://", "rtsps://")):
        raise ValueError("RTSP sources must begin with rtsp:// or rtsps://")


def build_video_source(source_type: str, source_url: str) -> VideoSource:
    validate_source_config(source_type, source_url)
    if source_type == "WEBCAM":
        return WebcamSource(camera_index=int(source_url.strip()))
    return VideoFileSource(source_url.strip())
