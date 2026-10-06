import os
import cv2 as cv
import asyncio
import base64
import json
import logging
import threading
from contextlib import suppress
from datetime import datetime, timezone
from typing import Dict, Any, List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.responses import StreamingResponse, Response
from db.database import SessionLocal
from db.models import Camera, RestrictedZone, SystemSetting, User
from ai_engine.pipeline.video_source import CameraSourceError, VideoFileSource, build_video_source
from ai_engine.pipeline.stream_processor import StreamProcessor
from ai_engine.zones.zone_detector import ZoneDetector
from ai_engine.crowd.crowd_detector import CrowdDetector
from services.event_service import EventService
from ai_engine.zones.zone_detector import point_in_polygon
from backend.app.api.v1.auth import get_current_user, get_user_from_token

router = APIRouter(prefix="/monitoring", tags=["Live Monitoring"])
logger = logging.getLogger(__name__)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)
logger.propagate = False
active_camera_streams = set()
active_camera_streams_lock = threading.Lock()

event_service = EventService()
zone_detector = ZoneDetector()
crowd_detector = CrowdDetector()

@router.get("/cameras")
def get_monitoring_cameras(user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        cams = db.query(Camera).order_by(Camera.created_at.desc()).all()
        return [c.to_dict() for c in cams]
    finally:
        db.close()


@router.get("/cameras/{camera_id}/snapshot")
def camera_snapshot(camera_id: str, user: User = Depends(get_current_user)):
    with active_camera_streams_lock:
        if camera_id in active_camera_streams:
            raise HTTPException(status_code=409, detail="Stop live monitoring before capturing a zone-drawing frame")
    db = SessionLocal()
    try:
        camera = db.query(Camera).filter(Camera.id == camera_id).first()
        if not camera:
            raise HTTPException(status_code=404, detail="Camera not found")
        source_url, source_type = camera.source_url, camera.source_type
    finally:
        db.close()
    source = build_video_source(source_type, source_url)
    try:
        if not source.is_opened():
            raise HTTPException(status_code=503, detail=source.error or "Configured camera source is unavailable")
        ok, frame = source.read_frame()
        if not ok or frame is None:
            raise HTTPException(status_code=503, detail=source.error or "Camera did not return a frame")
        encoded, image = cv.imencode(".jpg", frame)
        if not encoded:
            raise HTTPException(status_code=500, detail="Could not encode the camera frame")
        return Response(content=image.tobytes(), media_type="image/jpeg", headers={"X-Frame-Width": str(frame.shape[1]), "X-Frame-Height": str(frame.shape[0])})
    finally:
        source.release()

def _generate_mjpeg_frames(camera_id: str):
    """Generates multipart MJPEG stream frames for standard <img> tags."""
    db = SessionLocal()
    cam = None
    zones = []
    try:
        cam = db.query(Camera).filter(Camera.id == camera_id).first()
        if not cam:
            raise HTTPException(status_code=404, detail="Camera not found")
        if cam:
            zones = db.query(RestrictedZone).filter(RestrictedZone.camera_id == cam.id, RestrictedZone.is_active.is_(True)).all()
            threshold_setting = db.query(SystemSetting).filter(SystemSetting.key == "CROWD_THRESHOLD").first()
            crowd_threshold = int(threshold_setting.value) if threshold_setting else 10
    finally:
        db.close()

    source_url = cam.source_url
    source_type = cam.source_type

    source = build_video_source(source_type, source_url)

    if not source.is_opened():
        source.release()
        raise HTTPException(status_code=503, detail="Camera or video source is unavailable")

    processor = StreamProcessor(cache_ttl_seconds=3.0)
    zone_presence = set()
    active_occupancy_zones = set()
    crowd_active = False

    try:
        while True:
            ret, frame = source.read_frame()
            if not ret or frame is None:
                # Loop video file if ended
                if source_type != "WEBCAM":
                    source.release()
                    source = VideoFileSource(source_url)
                    if not source.cap.isOpened():
                        break
                    continue
                else:
                    break

            annotated_frame, detections, summary = processor.process_frame(frame)

            current_zone_presence = set()
            # Generate zone-access events only on observed entry transitions.
            for det in detections:
                for z in zones:
                    access = zone_detector.check_zone_access(
                        det["bbox"], det["role"], det["status"], z.get_polygon(), z.get_allowed_roles()
                    )
                    if not access:
                        continue
                    presence_key = (z.id, det.get("track_id"))
                    current_zone_presence.add(presence_key)
                    if presence_key not in zone_presence:
                        event_service.create_event(
                            event_type=access,
                            camera_id=cam.id,
                            zone_id=z.id,
                            track_id=det["track_id"],
                            member_id=det.get("member_id") if det["status"] == "VERIFIED" else None,
                            location=z.name,
                            description=f"{access.replace('_', ' ').title()} in zone '{z.name}'",
                            frame_snapshot=annotated_frame,
                        )
            zone_presence = current_zone_presence

            current_occupancy_zones = set()
            for z in zones:
                inside_count = sum(
                    1 for det in detections
                    if point_in_polygon(((det["bbox"][0] + det["bbox"][2]) // 2, det["bbox"][3]), z.get_polygon())
                )
                if inside_count > z.occupancy_threshold:
                    current_occupancy_zones.add(z.id)
                    if z.id not in active_occupancy_zones:
                        event_service.create_event(
                            event_type="CROWD_THRESHOLD_EXCEEDED",
                            camera_id=cam.id,
                            zone_id=z.id,
                            location=z.name,
                            description=f"Detected {inside_count} tracked people inside zone '{z.name}', above configured threshold {z.occupancy_threshold}",
                            frame_snapshot=annotated_frame,
                        )
            active_occupancy_zones = current_occupancy_zones

            # Check crowd threshold
            over_crowd_threshold = crowd_detector.check_crowd_threshold(summary["total"], crowd_threshold)
            if over_crowd_threshold and not crowd_active:
                event_service.create_event(
                    event_type="CROWD_THRESHOLD_EXCEEDED",
                    camera_id=cam.id if cam else None,
                    location=cam.location if cam else None,
                    description=f"Crowd count {summary['total']} exceeded configured threshold {crowd_threshold}",
                    frame_snapshot=annotated_frame
                )
            crowd_active = over_crowd_threshold

            ret, buffer = cv.imencode('.jpg', annotated_frame)
            if not ret:
                continue

            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
    finally:
        source.release()

def generate_mjpeg_frames(camera_id: str):
    with active_camera_streams_lock:
        if camera_id in active_camera_streams:
            raise HTTPException(status_code=409, detail="Camera is already being monitored")
        active_camera_streams.add(camera_id)
    try:
        yield from _generate_mjpeg_frames(camera_id)
    finally:
        with active_camera_streams_lock:
            active_camera_streams.discard(camera_id)

@router.get("/mjpeg/{camera_id}")
def mjpeg_stream(camera_id: str, user: User = Depends(get_current_user)):
    """MJPEG stream endpoint for high-performance direct video rendering."""
    return StreamingResponse(
        generate_mjpeg_frames(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@router.websocket("/ws/{camera_id}")
async def websocket_monitoring(websocket: WebSocket, camera_id: str):
    """WebSocket endpoint pushing JSON frames & live telemetry to browser dashboard."""
    subprotocols = websocket.scope.get("subprotocols", [])
    token_protocol = next((part for part in subprotocols if part.startswith("bearer.")), None)
    if not token_protocol:
        await websocket.close(code=4401, reason="Authentication required")
        return
    try:
        get_user_from_token(token_protocol[len("bearer."):])
    except HTTPException:
        await websocket.close(code=4401, reason="Authentication failed")
        return
    await websocket.accept(subprotocol="campus-security")
    logger.info("[LiveMonitoring] WebSocket connected for camera %s", camera_id)
    source = None
    reserved = False
    disconnect_task = asyncio.create_task(websocket.receive())

    def release_camera_source():
        nonlocal source
        if source is not None:
            current_source, source = source, None
            current_source.release()

    def release_stream_resources():
        nonlocal reserved
        try:
            release_camera_source()
        finally:
            if reserved:
                with active_camera_streams_lock:
                    active_camera_streams.discard(camera_id)
                reserved = False

    def consume_control_message():
        nonlocal disconnect_task
        if not disconnect_task.done():
            return None
        try:
            message = disconnect_task.result()
        except WebSocketDisconnect:
            return "disconnect"
        if message.get("type") == "websocket.disconnect":
            return "disconnect"
        if message.get("type") == "websocket.receive" and message.get("text"):
            try:
                if json.loads(message["text"]).get("type") == "stop":
                    return "stop"
            except (TypeError, ValueError):
                pass
        disconnect_task = asyncio.create_task(websocket.receive())
        return None

    async def acknowledge_stop():
        release_stream_resources()
        await websocket.send_text(json.dumps({"type": "stopped", "camera_id": camera_id}))
        await websocket.close(code=1000, reason="Monitoring stopped")

    try:
        db = SessionLocal()
        try:
            cam = db.query(Camera).filter(Camera.id == camera_id).first()
            if not cam:
                await websocket.send_text(json.dumps({"type": "error", "code": "CAMERA_NOT_FOUND", "message": "Camera was not found."}))
                await websocket.close(code=4404, reason="Camera not found")
                return
            source_url, source_type, location = cam.source_url, cam.source_type, cam.location
            zones = db.query(RestrictedZone).filter(
                RestrictedZone.camera_id == cam.id,
                RestrictedZone.is_active.is_(True),
            ).all()
            zones = [{"id": z.id, "name": z.name, "polygon": z.get_polygon(), "allowed_roles": z.get_allowed_roles(), "occupancy_threshold": z.occupancy_threshold}
                     for z in zones]
            threshold_setting = db.query(SystemSetting).filter(
                SystemSetting.key == "CROWD_THRESHOLD"
            ).first()
            crowd_threshold = int(threshold_setting.value) if threshold_setting else 10
            was_online = cam.status == "ONLINE"
        finally:
            db.close()

        with active_camera_streams_lock:
            already_active = camera_id in active_camera_streams
            if not already_active:
                active_camera_streams.add(camera_id)
                reserved = True
        if already_active:
            await websocket.send_text(json.dumps({"type": "error", "code": "CAMERA_ALREADY_MONITORED", "message": "This camera already has an active processing stream."}))
            await websocket.close(code=4409, reason="Camera is already being monitored")
            return

        if source_type == "WEBCAM":
            logger.info("[LiveMonitoring] Opening configured webcam index %s", source_url)
        source = build_video_source(source_type, source_url)

        if not source.is_opened():
            source_error = source.error or "OpenCV could not open the configured source"
            release_camera_source()
            db = SessionLocal()
            try:
                camera = db.query(Camera).filter(Camera.id == camera_id).first()
                if camera:
                    camera.status = "OFFLINE"
                    db.commit()
            finally:
                db.close()
            event_service.create_event("CAMERA_OFFLINE", camera_id=camera_id, location=location,
                                       description=source_error)
            release_stream_resources()
            await websocket.send_text(json.dumps({
                "type": "error",
                "code": "CAMERA_SOURCE_UNAVAILABLE",
                "message": source_error,
                "source_status": "OFFLINE",
            }))
            await websocket.close(code=4403, reason=source_error[:120])
            return

        if source_type == "WEBCAM":
            logger.info(
                "[LiveMonitoring] Webcam index %s selected backend %s",
                source_url,
                getattr(source, "backend_name", "unknown"),
            )

        db = SessionLocal()
        try:
            camera = db.query(Camera).filter(Camera.id == camera_id).first()
            if camera:
                camera.status = "ONLINE"
                camera.last_seen = datetime.now(timezone.utc)
                db.commit()
        finally:
            db.close()

        if not was_online:
            await asyncio.to_thread(
                event_service.create_event,
                event_type="CAMERA_ONLINE",
                camera_id=camera_id,
                location=location,
                description="Configured camera source opened successfully",
            )

        processor = StreamProcessor(cache_ttl_seconds=3.0)
        logger.info("[LiveMonitoring] Streaming started for camera %s", camera_id)
        last_frame_time = 0.0
        logged_first_frame = False
        zone_presence = set()
        active_occupancy_zones = set()
        crowd_active = False
        consecutive_failed_frames = 0
        max_consecutive_failed_frames = 5 if source_type == "WEBCAM" else 1
        while True:
            control = consume_control_message()
            if control == "disconnect":
                break
            if control == "stop":
                await acknowledge_stop()
                break
            ret, frame = await asyncio.to_thread(source.read_frame)
            if not ret or frame is None:
                consecutive_failed_frames += 1
                logger.warning(
                    "[LiveMonitoring] Camera %s read failed (attempt %s/%s): %s",
                    camera_id,
                    consecutive_failed_frames,
                    max_consecutive_failed_frames,
                    source.error or "frame read failed",
                )
                if source_type != "WEBCAM":
                    if consecutive_failed_frames >= max_consecutive_failed_frames:
                        source.release()
                        source = VideoFileSource(source_url)
                        if source.is_opened():
                            consecutive_failed_frames = 0
                            continue
                        raise CameraSourceError(source.error or "Configured video source could not be restarted")
                    await asyncio.sleep(0.1)
                    continue
                if consecutive_failed_frames >= max_consecutive_failed_frames:
                    raise CameraSourceError(
                        source.error or f"Webcam {source_url} is unavailable or not returning valid frames."
                    )
                await asyncio.sleep(0.1)
                continue

            consecutive_failed_frames = 0
            if not logged_first_frame:
                logger.info(
                    "[LiveMonitoring] First frame captured for camera %s (%sx%s)",
                    camera_id,
                    frame.shape[1],
                    frame.shape[0],
                )
                logged_first_frame = True

            annotated_frame, detections, summary = await asyncio.to_thread(processor.process_frame, frame)
            control = consume_control_message()
            if control == "disconnect":
                break
            if control == "stop":
                await acknowledge_stop()
                break
            emitted_events = []
            current_zone_presence = set()
            for detection in detections:
                if detection["status"] == "VERIFIED":
                    event = await asyncio.to_thread(
                        event_service.create_event,
                        event_type="PERSON_VERIFIED",
                        camera_id=camera_id,
                        track_id=detection["track_id"],
                        member_id=detection.get("member_id"),
                        location=location,
                        description=f"Verified enrolled member {detection.get('name') or ''}".strip(),
                        frame_snapshot=annotated_frame,
                    )
                    if event:
                        emitted_events.append(event)
                elif detection["status"] == "UNKNOWN":
                    event = await asyncio.to_thread(
                        event_service.create_event,
                        event_type="UNKNOWN_PERSON",
                        camera_id=camera_id,
                        track_id=detection["track_id"],
                        location=location,
                        description="No enrolled member matched this face",
                        frame_snapshot=annotated_frame,
                    )
                    if event:
                        emitted_events.append(event)
                for zone in zones:
                    access = zone_detector.check_zone_access(
                        detection["bbox"], detection["role"], detection["status"],
                        zone["polygon"], zone["allowed_roles"],
                    )
                    if access:
                        presence_key = (zone["id"], detection.get("track_id"))
                        current_zone_presence.add(presence_key)
                    else:
                        continue
                    if access and presence_key not in zone_presence:
                        event = await asyncio.to_thread(
                            event_service.create_event,
                            event_type=access,
                            camera_id=camera_id,
                            zone_id=zone["id"],
                            track_id=detection["track_id"],
                            member_id=detection.get("member_id") if detection["status"] == "VERIFIED" else None,
                            location=zone["name"],
                            description=(
                                f"Unauthorized access detected in zone '{zone['name']}'"
                                if access == "UNAUTHORIZED_ZONE_ACCESS"
                                else f"Authorized zone entry detected in '{zone['name']}'"
                            ),
                            frame_snapshot=annotated_frame,
                        )
                        if event:
                            emitted_events.append(event)
            zone_presence = current_zone_presence

            current_occupancy_zones = set()
            for zone in zones:
                inside_count = sum(
                    1 for detection in detections
                    if point_in_polygon(((detection["bbox"][0] + detection["bbox"][2]) // 2, detection["bbox"][3]), zone["polygon"])
                )
                if inside_count > zone["occupancy_threshold"]:
                    current_occupancy_zones.add(zone["id"])
                    if zone["id"] not in active_occupancy_zones:
                        event = await asyncio.to_thread(
                            event_service.create_event,
                            event_type="CROWD_THRESHOLD_EXCEEDED",
                            camera_id=camera_id,
                            zone_id=zone["id"],
                            location=zone["name"],
                            description=f"Detected {inside_count} tracked people inside zone '{zone['name']}', above configured threshold {zone['occupancy_threshold']}",
                            frame_snapshot=annotated_frame,
                        )
                        if event:
                            emitted_events.append(event)
            active_occupancy_zones = current_occupancy_zones

            over_crowd_threshold = crowd_detector.check_crowd_threshold(summary["total"], crowd_threshold)
            if over_crowd_threshold and not crowd_active:
                event = await asyncio.to_thread(
                    event_service.create_event,
                    event_type="CROWD_THRESHOLD_EXCEEDED",
                    camera_id=camera_id,
                    location=location,
                    description=f"Detected count {summary['total']} reached crowd threshold {crowd_threshold}",
                    frame_snapshot=annotated_frame,
                )
                if event:
                    emitted_events.append(event)
            crowd_active = over_crowd_threshold

            encoded, buffer = cv.imencode('.jpg', annotated_frame)
            if encoded:
                payload = {
                    "type": "telemetry",
                    "data": {
                        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                        "camera_id": camera_id,
                        "frame_number": processor.frame_number,
                        "frame": f"data:image/jpeg;base64,{base64.b64encode(buffer).decode('ascii')}",
                        "fps": round(processor.fps, 1),
                        "summary": summary,
                        "person_count": summary["total"],
                        "detections": detections,
                        "events": emitted_events,
                        "source_status": "LIVE",
                    },
                }
                await websocket.send_text(json.dumps(payload))
            interval = 1.0 / processor.max_processing_fps
            now = asyncio.get_running_loop().time()
            await asyncio.sleep(max(0, interval - (now - last_frame_time)))
            last_frame_time = asyncio.get_running_loop().time()
    except WebSocketDisconnect:
        logger.info("Monitoring client disconnected for camera %s", camera_id)
    except Exception as exc:
        if isinstance(exc, RuntimeError) and "Unexpected ASGI message 'websocket.send'" in str(exc):
            logger.info("Monitoring client disconnected during frame delivery for camera %s", camera_id)
            return
        logger.exception("Monitoring failed for camera %s", camera_id)
        code = "CAMERA_SOURCE_UNAVAILABLE" if isinstance(exc, CameraSourceError) else "MONITORING_PROCESSING_ERROR"
        public_message = (
            str(exc)
            if code == "CAMERA_SOURCE_UNAVAILABLE"
            else "Live monitoring processing failed. Check backend logs and retry."
        )
        release_camera_source()
        db = SessionLocal()
        try:
            camera = db.query(Camera).filter(Camera.id == camera_id).first()
            if camera:
                camera.status = "OFFLINE" if code == "CAMERA_SOURCE_UNAVAILABLE" else "ERROR"
                db.commit()
        except Exception:
            db.rollback()
            logger.exception("Could not update camera status for %s", camera_id)
        finally:
            db.close()
        if code == "CAMERA_SOURCE_UNAVAILABLE":
            await asyncio.to_thread(
                event_service.create_event,
                event_type="CAMERA_OFFLINE",
                camera_id=camera_id,
                location=locals().get("location"),
                description=public_message,
            )
        release_stream_resources()
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "code": code,
                "message": public_message,
                "source_status": "OFFLINE" if code == "CAMERA_SOURCE_UNAVAILABLE" else "ERROR",
            }))
            await websocket.close(
                code=4403 if code == "CAMERA_SOURCE_UNAVAILABLE" else 1011,
                reason="Camera source unavailable" if code == "CAMERA_SOURCE_UNAVAILABLE" else "Monitoring processing failed",
            )
        except Exception:
            pass
    finally:
        if disconnect_task and not disconnect_task.done():
            disconnect_task.cancel()
            with suppress(asyncio.CancelledError):
                await disconnect_task
        release_stream_resources()
        logger.info("[LiveMonitoring] Processing stopped for camera %s", camera_id)
