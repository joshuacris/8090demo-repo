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

import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, Cookie
from sqlalchemy.orm import Session as DBSession
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from .models import User, Session
from .database import get_db

SESSION_COOKIE = "vault_session"
SESSION_TTL = timedelta(days=7)

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
def register(payload: RegisterRequest, db: DBSession = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(email=payload.email, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "email": user.email}


@router.post("/api/auth/login")
def login(payload: LoginRequest, response: Response, db: DBSession = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    # Create a server-side session and hand the client an opaque cookie.
    sess = issue_session(user, db)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=sess.id,
        httponly=True,      # JS can't read it -> mitigates XSS token theft
        secure=True,        # only sent over HTTPS
        samesite="lax",
        max_age=int(SESSION_TTL.total_seconds()),
    )
    return {"status": "logged in"}


@router.post("/api/auth/logout")
def logout(
    response: Response,
    db: DBSession = Depends(get_db),
    vault_session: str | None = Cookie(default=None),
):
    # Server-side revocation: just delete the session row. Instantly invalid.
    if vault_session:
        db.query(Session).filter(Session.id == vault_session).delete()
        db.commit()
    response.delete_cookie(SESSION_COOKIE)
    return {"status": "logged out"}


# --- Session-based auth implementation (PR Y) ---

def issue_session(user: User, db: DBSession) -> Session:
    """Create a server-side session row with a random opaque id."""
    sess = Session(
        id=secrets.token_urlsafe(32),
        user_id=user.id,
        expires_at=datetime.utcnow() + SESSION_TTL,
    )
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return sess


def get_current_user(
    db: DBSession = Depends(get_db),
    vault_session: str | None = Cookie(default=None),
) -> User:
    """Resolve the user by looking up their session in the DB.

    Every request costs one DB lookup, but revocation is instant and we can
    list/kill active sessions per user.
    """
    if not vault_session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    sess = db.query(Session).filter(Session.id == vault_session).first()
    if not sess:
        raise HTTPException(status_code=401, detail="Invalid session")
    if sess.expires_at < datetime.utcnow():
        db.delete(sess)
        db.commit()
        raise HTTPException(status_code=401, detail="Session expired")
    return sess.user
