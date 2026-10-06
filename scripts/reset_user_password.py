"""Development utility to reset a KLU admin/officer password interactively."""
import getpass
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from db.database import SessionLocal
from db.models import User
from services.auth_service import hash_password


ACCOUNTS = {
    "admin": ("admin@klu.ac.in", "ADMIN"),
    "officer": ("officer@klu.ac.in", "SECURITY_OFFICER"),
}


def main():
    account = input("Reset which account (admin/officer)? ").strip().lower()
    if account not in ACCOUNTS:
        raise SystemExit("Choose admin or officer.")

    password = getpass.getpass("New password: ")
    confirmation = getpass.getpass("Confirm new password: ")
    if not password or password != confirmation:
        raise SystemExit("Passwords must be non-empty and match.")

    email, role = ACCOUNTS[account]
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email.ilike(email), User.role == role).one_or_none()
        if user is None:
            raise SystemExit(f"No {account} account found for {email}.")
        user.hashed_password = hash_password(password)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    print(f"Password updated for {email}.")


if __name__ == "__main__":
    main()
