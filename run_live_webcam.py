import os
import sys
import argparse
import cv2 as cv

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from db.database import init_db
from services.enrollment_service import EnrollmentService
from ai_engine.pipeline.video_source import WebcamSource, VideoFileSource
from ai_engine.pipeline.stream_processor import StreamProcessor

def ensure_charan_sai_enrolled():
    init_db()
    service = EnrollmentService()
    # Check if Charan Sai is already enrolled
    from db.database import SessionLocal
    from db.models import CollegeMember
    db = SessionLocal()
    try:
        member = db.query(CollegeMember).filter(CollegeMember.college_id == "CS-2026-001").first()
        if member and member.face_enrolled:
            print("[LiveWebcam] Member 'Charan Sai' (CS-2026-001) is enrolled in Database.")
            return
    finally:
        db.close()

    print("[LiveWebcam] Enrolling test user 'Charan Sai' into Database...")
    # Seed face crop from video or synthetic test pattern
    video_path = "test_datas/testing_video.mp4"
    img = None
    if os.path.exists(video_path):
        cap = cv.VideoCapture(video_path)
        for idx in range(15):
            ret, frame = cap.read()
            if ret and idx == 10:
                img = frame
                break
        cap.release()

    res = service.enroll_member(
        name="Charan Sai",
        college_id="CS-2026-001",
        role="Student",
        image_input=img,
        department="Computer Science",
        year="4th Year"
    )
    print(f"[LiveWebcam] Enrollment result: {res.get('success')}")

def main():
    parser = argparse.ArgumentParser(description="Live Webcam & Video Face Verification Platform")
    parser.add_argument("--webcam", action="store_true", default=True, help="Use laptop webcam index 0")
    parser.add_argument("--video", type=str, help="Use recorded MP4 video file")
    parser.add_argument("--cam-id", "--cam_id", dest="cam_id", type=int, default=0, help="Webcam device index (default: 0)")
    parser.add_argument("--max-frames", "--max_frames", dest="max_frames", type=int, default=0, help="Max frames to process (0 = infinite)")
    parser.add_argument("--save-output", "--save_output", dest="save_output", type=str, help="Optional output MP4 file path to save rendered video")
    args = parser.parse_args()

    ensure_charan_sai_enrolled()

    if args.video and os.path.exists(args.video):
        print(f"[LiveWebcam] Processing video file: {args.video}")
        source = VideoFileSource(args.video)
    else:
        print(f"[LiveWebcam] Initializing live webcam stream (Index: {args.cam_id})...")
        source = WebcamSource(camera_index=args.cam_id)

    processor = StreamProcessor(cache_ttl_seconds=3.0)

    writer = None
    frame_count = 0

    print("[LiveWebcam] Starting live processing loop. Press 'q' or ESC in window to exit.")

    try:
        while True:
            ret, frame = source.read_frame()
            if not ret or frame is None:
                print("[LiveWebcam] Stream ended or frame unavailable.")
                break

            frame_count += 1

            annotated_frame, detections, summary = processor.process_frame(frame)

            # Initialize video writer if save_output is specified
            if args.save_output and writer is None:
                h, w, _ = annotated_frame.shape
                fourcc = cv.VideoWriter_fourcc(*'mp4v')
                writer = cv.VideoWriter(args.save_output, fourcc, 20.0, (w, h))

            if writer is not None:
                writer.write(annotated_frame)

            # Display window unless running headlessly
            try:
                cv.imshow("Campus Security - Intelligent CCTV Live Monitoring", annotated_frame)
                key = cv.waitKey(1) & 0xFF
                if key == ord('q') or key == 27:
                    print("[LiveWebcam] User exit requested.")
                    break
            except cv.error:
                # Headless environment handling
                if frame_count % 30 == 0:
                    print(f"[Frame {frame_count}] Detections: {summary}")

            if args.max_frames > 0 and frame_count >= args.max_frames:
                print(f"[LiveWebcam] Processed maximum target frames ({args.max_frames}). Stopping.")
                break

    finally:
        source.release()
        if writer is not None:
            writer.release()
        cv.destroyAllWindows()
        print(f"[LiveWebcam] Processing complete. Total frames: {frame_count}")

if __name__ == "__main__":
    main()
