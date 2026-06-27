"""Authentication foundation.

This module sets up the *shared* pieces every auth strategy needs:
- User registration with hashed passwords
- Password verification on login

What it deliberately does NOT decide yet: HOW we keep a user logged in after
login (the session/token mechanism). `issue_token()` and `get_current_user()`
are intentionally left as stubs — the follow-up PRs fill these in two different
ways so we can compare them:
  - PR Y: server-side sessions (stateful, cookie -> session row in DB)
  - PR Z: JWT (stateless, signed token, no server state)
"""

from datetime import datetime, timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from .models import User
from .config import settings
from .database import get_db

ACCESS_TTL = timedelta(minutes=15)
bearer_scheme = HTTPBearer(auto_error=False)

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(raw: str) -> str:
    return pwd_context.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    return pwd_context.verify(raw, hashed)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/api/auth/register")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(email=payload.email, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "email": user.email}


@router.post("/api/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    # Sign a stateless JWT. No server-side record is kept.
    token = issue_token(user)
    return {"access_token": token, "token_type": "bearer"}


# --- JWT-based auth implementation (PR Z) ---

def issue_token(user: User) -> str:
    """Sign a short-lived JWT carrying the user id. Stateless: nothing stored."""
    now = datetime.utcnow()
    payload = {
        "sub": str(user.id),
        "iat": now,
        "exp": now + ACCESS_TTL,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the user by verifying the JWT signature. No DB lookup for the
    token itself — only to load the user object. Fully stateless and horizontally
    scalable, but tokens can't be revoked before they expire.
    """
    if creds is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(
            creds.credentials,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
