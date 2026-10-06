import csv
import io
from fastapi import APIRouter, Response
from db.database import SessionLocal
from db.models import SecurityEvent, timestamp_iso_utc

router = APIRouter(prefix="/reports", tags=["Reports"])

@router.get("/export/csv")
def export_csv_report():
    db = SessionLocal()
    try:
        events = db.query(SecurityEvent).order_by(SecurityEvent.timestamp.desc()).all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Event ID", "Timestamp", "Event Type", "Severity", "Location", "Member Name", "Status", "Description"])

        for e in events:
            writer.writerow([
                e.id,
                timestamp_iso_utc(e.timestamp) or "",
                e.event_type,
                e.severity,
                e.location or "",
                e.member.name if e.member else "UNKNOWN/UNVERIFIED",
                e.status,
                e.description or ""
            ])

        response = Response(content=output.getvalue(), media_type="text/csv")
        response.headers["Content-Disposition"] = "attachment; filename=campus_security_audit_report.csv"
        return response
    finally:
        db.close()
