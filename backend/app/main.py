import os
import sys
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

# Ensure parent path is registered
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from db.database import init_db, engine
from backend.app.api.v1.auth import get_current_user
from backend.app.api.v1 import (
    auth, dashboard, cameras, members, zones,
    events, alerts, analytics, reports, settings, monitoring, identification, notifications, audit
)

app = FastAPI(
    title="CampusShield — AI Campus Security & Intelligent CCTV Platform",
    description="Backend API services for AI-powered person tracking, face verification, restricted zone authorization, and alert management.",
    version="2.0.0"
)

allowed_origins = [origin.strip() for origin in os.getenv(
    "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Database on Startup
@app.on_event("startup")
def on_startup():
    try:
        init_db()
    except Exception as exc:
        raise RuntimeError(f"Database initialization failed: {exc}") from exc
    print("[Security Platform] Database initialized successfully.")

# Keep biometric crops and event snapshots behind authenticated API routes.
snapshots_dir = os.path.join("data", "snapshots")
enrollments_dir = os.path.join("data", "enrollments")
os.makedirs(snapshots_dir, exist_ok=True)
os.makedirs(enrollments_dir, exist_ok=True)

# Register V1 API Routers
app.include_router(auth.router, prefix="/api/v1")
auth_required = [Depends(get_current_user)]
app.include_router(dashboard.router, prefix="/api/v1", dependencies=auth_required)
app.include_router(cameras.router, prefix="/api/v1", dependencies=auth_required)
app.include_router(members.router, prefix="/api/v1", dependencies=auth_required)
app.include_router(identification.router, prefix="/api/v1", dependencies=auth_required)
app.include_router(zones.router, prefix="/api/v1", dependencies=auth_required)
app.include_router(events.router, prefix="/api/v1", dependencies=auth_required)
app.include_router(alerts.router, prefix="/api/v1", dependencies=auth_required)
app.include_router(analytics.router, prefix="/api/v1", dependencies=auth_required)
app.include_router(reports.router, prefix="/api/v1", dependencies=auth_required)
app.include_router(settings.router, prefix="/api/v1", dependencies=auth_required)
app.include_router(notifications.router, prefix="/api/v1", dependencies=auth_required)
app.include_router(audit.router, prefix="/api/v1", dependencies=auth_required)
app.include_router(monitoring.router, prefix="/api/v1")

@app.get("/healthz")
def health_check():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ONLINE", "database": "ONLINE"}

@app.get("/")
def root():
    return {
        "status": health_check()["status"],
        "system": "CampusShield AI Security Platform",
        "version": "2.0.0",
        "docs": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
