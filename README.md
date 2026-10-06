# CampusShield

CampusShield is an AI-powered campus security and intelligent CCTV platform. It provides a React dashboard backed by a FastAPI service for camera monitoring, member management, face verification, restricted zones, security events, alerts, analytics, reports, and audit records.

## Technology

- **Backend:** Python 3.11, FastAPI, SQLAlchemy, SQLite by default (PostgreSQL supported)
- **Frontend:** React, TypeScript, Vite, Tailwind CSS
- **AI and video:** YOLOv8, FaceNet, OpenCV, ByteTrack, and Supervision

## Repository layout

- `backend/` — FastAPI application and versioned API routes
- `frontend/` — React dashboard
- `ai_engine/` — face/person detection, tracking, streaming, and zone processing
- `db/` — SQLAlchemy database models and setup
- `services/` — authentication, enrollment, event, alert, and notification services
- `facenet_files/`, `supervision/` — source modules used by the existing recognition and tracking pipeline
- `yolo_models/` — YOLO person and face detector weights used by the application
- `scripts/` — database bootstrap and maintenance utilities
- `tests/` — backend and AI-related tests
- `data/enrollments/` — local enrollment data directory; private images are not tracked

## Run locally on Windows

### Backend

From the repository root, create and activate a Python 3.11 environment, then install the runtime dependencies:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-runtime.txt
Copy-Item .env.example .env
```

Edit `.env` before starting the service. Set a unique `JWT_SECRET` and configure `DATABASE_URL` if using PostgreSQL. The default database is local SQLite at `data/campushield.db`; it is created at startup and is intentionally excluded from Git.

Start the API:

```powershell
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

The API documentation is available at `http://127.0.0.1:8000/docs`, and the health endpoint is `http://127.0.0.1:8000/healthz`.

To create an initial administrator or security-officer account, set the corresponding `CAMPUSHIELD_BOOTSTRAP_ADMIN_*` or `CAMPUSHIELD_BOOTSTRAP_SECURITY_OFFICER_*` email and password environment variables, then run:

```powershell
python scripts/seed_initial_data.py
```

Bootstrap passwords must be supplied locally and must never be committed.

### Frontend

In a second terminal:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Open the local URL printed by Vite. The Vite development server proxies API requests to the backend.

## Configuration and privacy

- `.env.example` documents configuration names only. Copy it to `.env` and replace the placeholder values locally; `.env` is ignored by Git.
- `yolo_models/yolov8n-face.pt` and `yolo_models/yolov8n.pt` are the application detector weights and are included in the repository. They are approximately 6 MB each, below GitHub's per-file size limit.
- The legacy standalone `main.py` attendance pipeline additionally loads `facenet_models/new_classifier_Jun27_759.pkl`. That classifier is trained on face embeddings and contains enrolled-person labels, so it is intentionally not published. The `facenet_models/*.pkl` ignore rule keeps the local artifact private; that legacy pipeline requires the locally provided model file.
- Enrollment photos, biometric crops, camera snapshots, local databases, generated attendance exports, environment files, and runtime outputs are excluded by `.gitignore`. Do not add real enrollment images or biometric data to the repository.

## Tests and frontend build

From the repository root:

```powershell
python -m pytest
```

For a production frontend build:

```powershell
Set-Location frontend
npm ci
npm run build
```
