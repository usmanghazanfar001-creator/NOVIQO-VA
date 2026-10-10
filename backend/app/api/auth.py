import hashlib, logging, secrets
from datetime import timedelta
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.auth import check_pw, current_user, hash_pw, set_session, COOKIE
from ..core.limits import limiter
from ..database.db import get_db
from ..models.models import PasswordReset, User, _now
from ..services.email import fire_and_forget, send_email
import os

log = logging.getLogger("noviqo.auth")
router = APIRouter(prefix="/api/auth")
Email = Annotated[str, Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=255)]
Password = Annotated[str, Field(min_length=8, max_length=128)]

class SignupIn(BaseModel): email: Email; password: Password; name: str = Field("", max_length=100)
class LoginIn(BaseModel): email: Email; password: str = Field(max_length=128)
class ForgotIn(BaseModel): email: Email
class ResetIn(BaseModel): token: str = Field(max_length=200); password: Password
class ProfileIn(BaseModel): name: str = Field(max_length=100)

def public(u: User) -> dict: return {"id": u.id, "email": u.email, "name": u.name}
def send_reset_email(email: str, link: str):
    """Emails the link (or logs it when SMTP isn't configured). Never return the token in a response."""
    fire_and_forget(send_email(email, "Reset your NOVIQO password", f"Use this link to choose a new password (valid for 1 hour):\n{link}\n\nIf you didn't ask for this, ignore this email."))

@router.post("/signup")
@limiter.limit("10/minute")
async def signup(request: Request, response: Response, body: SignupIn, db: AsyncSession = Depends(get_db)):
    email = body.email.lower()
    if await db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with that email already exists.")
    u = User(email=email, name=body.name.strip(), password_hash=hash_pw(body.password))
    db.add(u); await db.commit(); set_session(response, u.id)
    return public(u)

@router.post("/login")
@limiter.limit("10/minute")
async def login(request: Request, response: Response, body: LoginIn, db: AsyncSession = Depends(get_db)):
    u = await db.scalar(select(User).where(User.email == body.email.lower()))
    if not u or not check_pw(u.password_hash, body.password):
        raise HTTPException(401, "Incorrect email or password.")
    set_session(response, u.id); return public(u)

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(COOKIE); return {"ok": True}

@router.get("/me")
async def me(user: User = Depends(current_user)): return public(user)

@router.patch("/me")
async def update_me(body: ProfileIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    user.name = body.name.strip(); await db.commit(); return public(user)

@router.post("/forgot")
@limiter.limit("5/minute")
async def forgot(request: Request, body: ForgotIn, db: AsyncSession = Depends(get_db)):
    u = await db.scalar(select(User).where(User.email == body.email.lower()))
    if u:  # same response either way, so the endpoint can't be used to discover accounts
        tok = secrets.token_urlsafe(32)
        db.add(PasswordReset(user_id=u.id, token_hash=hashlib.sha256(tok.encode()).hexdigest(), expires_at=_now() + timedelta(hours=1)))
        await db.commit()
        send_reset_email(u.email, f"{os.getenv('APP_URL', 'http://localhost:5173')}/reset?token={tok}")
    return {"ok": True}

@router.post("/reset")
@limiter.limit("10/minute")
async def reset(request: Request, body: ResetIn, db: AsyncSession = Depends(get_db)):
    r = await db.scalar(select(PasswordReset).where(PasswordReset.token_hash == hashlib.sha256(body.token.encode()).hexdigest()))
    if not r or r.used or r.expires_at < _now(): raise HTTPException(400, "This reset link is invalid or has expired.")
    (await db.get(User, r.user_id)).password_hash = hash_pw(body.password); r.used = True
    await db.commit(); return {"ok": True}
