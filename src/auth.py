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

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from .models import User
from .database import get_db

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
    # TODO(auth-mechanism): issue a real credential here.
    #   PR Y will create a server-side session + set a cookie.
    #   PR Z will sign and return a JWT.
    token = issue_token(user)
    return {"token": token}


# --- STUBS to be implemented by the chosen auth strategy (PR Y or PR Z) ---

def issue_token(user: User) -> str:
    """Issue a credential for a freshly-authenticated user.

    STUB — returns a placeholder. Real implementation comes in PR Y / PR Z.
    """
    return f"placeholder-token-for-user-{user.id}"


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Resolve the authenticated user for a request.

    STUB — currently trusts an `X-User-Id` header so the rest of the app can be
    wired up. This is NOT secure and must be replaced by PR Y / PR Z.
    """
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
