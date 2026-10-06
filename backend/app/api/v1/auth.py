from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, field_validator
from typing import Optional
from sqlalchemy import func
from db.database import SessionLocal
from db.models import User
from services.auth_service import verify_password, create_jwt_token, decode_jwt_token, hash_password, is_legacy_password_hash

router = APIRouter(prefix="/auth", tags=["Authentication"])

class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def require_klu_email(cls, value: str) -> str:
        email = value.strip().lower()
        if not email.endswith("@klu.ac.in") or email.count("@") != 1 or not email.split("@", 1)[0]:
            raise ValueError("Use your institutional @klu.ac.in email address")
        return email

def get_user_from_token(token: str) -> User:
    payload = decode_jwt_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == payload.get("user_id")).first()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User account is inactive or disabled")
        return user
    finally:
        db.close()

def get_current_user(authorization: Optional[str] = Header(None)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authentication token")
    return get_user_from_token(authorization.split(" ", 1)[1])


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Administrator privileges are required")
    return user

@router.post("/login")
def login(req: LoginRequest):
    db = SessionLocal()
    try:
        email = req.email
        user = db.query(User).filter(func.lower(User.email) == email).first()
        if not user or not verify_password(req.password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        if is_legacy_password_hash(user.hashed_password):
            user.hashed_password = hash_password(req.password)
            db.commit()

        token = create_jwt_token({"user_id": user.id, "username": user.username, "role": user.role})
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": user.to_dict()
        }
    finally:
        db.close()

@router.get("/me")
def get_me(user: User = Depends(get_current_user)):
    return user.to_dict()
