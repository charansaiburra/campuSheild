import os
import sys

# Ensure parent directory is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from db.database import init_db, SessionLocal
from db.models import User, SystemSetting
from services.auth_service import hash_password

LEGACY_ACCOUNT_EMAILS = {
    ("ADMIN", "admin@campus.edu"): "admin@klu.ac.in",
    ("SECURITY_OFFICER", "officer@campus.edu"): "officer@klu.ac.in",
}
BOOTSTRAP_EMAILS = {
    "ADMIN": "admin@klu.ac.in",
    "SECURITY_OFFICER": "officer@klu.ac.in",
}

def _migrate_institutional_emails(db):
    migrated = 0
    for (role, old_email), new_email in LEGACY_ACCOUNT_EMAILS.items():
        user = db.query(User).filter(User.role == role, User.email.ilike(old_email)).first()
        if not user:
            continue
        conflict = db.query(User).filter(User.email.ilike(new_email), User.id != user.id).first()
        if conflict:
            raise RuntimeError(f"Cannot migrate {role}: {new_email} is already assigned to another account")
        user.email = new_email
        migrated += 1
    return migrated

def _seed_configured_user(db, role: str, prefix: str):
    email = os.getenv(f"CAMPUSHIELD_BOOTSTRAP_{prefix}_EMAIL", "").strip().lower()
    password = os.getenv(f"CAMPUSHIELD_BOOTSTRAP_{prefix}_PASSWORD", "")
    if not email and not password:
        return False
    if not email or not password:
        raise RuntimeError(f"Set both CAMPUSHIELD_BOOTSTRAP_{prefix}_EMAIL and CAMPUSHIELD_BOOTSTRAP_{prefix}_PASSWORD")
    expected_email = BOOTSTRAP_EMAILS[role]
    if email != expected_email:
        raise RuntimeError(f"CAMPUSHIELD_BOOTSTRAP_{prefix}_EMAIL must be {expected_email}")
    username = os.getenv(f"CAMPUSHIELD_BOOTSTRAP_{prefix}_USERNAME", email.split("@", 1)[0]).strip()
    existing_email = db.query(User).filter(User.email.ilike(email)).first()
    if existing_email:
        return False
    existing_username = db.query(User).filter(User.username == username).first()
    if existing_username and existing_username.role == role and existing_username.email.lower() == email:
        return False
    if existing_username:
        raise RuntimeError(f"Bootstrap username '{username}' is already assigned to another account")
    db.add(User(username=username, email=email, hashed_password=hash_password(password), role=role))
    return True

def seed_data():
    try:
        init_db()
    except Exception as exc:
        raise RuntimeError(f"Database initialization failed while seeding: {exc}") from exc
    db = SessionLocal()
    try:
        migrated = _migrate_institutional_emails(db)
        print(f"[Seeder] Migrated {migrated} legacy institutional account email(s).")
        print("[Seeder] Creating only explicitly configured bootstrap accounts...")
        created_admin = _seed_configured_user(db, "ADMIN", "ADMIN")
        created_officer = _seed_configured_user(db, "SECURITY_OFFICER", "SECURITY_OFFICER")
        if not created_admin and not created_officer:
            print("[Seeder] No bootstrap accounts configured; existing users were preserved.")

        # System settings
        settings = [
            ("FACE_VERIFICATION_THRESHOLD", "0.60", "Cosine similarity threshold for face verification"),
            ("CROWD_THRESHOLD", "10", "Number of people that triggers a crowd event"),
            ("CROWD_ALERT_COOLDOWN_SECONDS", "30", "Cooldown period between duplicate crowd alerts"),
            ("ZONE_BREACH_COOLDOWN_SECONDS", "15", "Cooldown period between duplicate zone breach alerts")
        ]
        for key, val, desc in settings:
            s = db.query(SystemSetting).filter(SystemSetting.key == key).first()
            if not s:
                db.add(SystemSetting(key=key, value=val, description=desc))

        db.commit()
        print("[Seeder] Database successfully initialized and seeded.")
    except Exception as e:
        db.rollback()
        raise RuntimeError(f"Seed operation failed: {e}") from e
    finally:
        db.close()

    # Face enrollment is intentionally left to the member enrollment workflow.

if __name__ == "__main__":
    seed_data()
