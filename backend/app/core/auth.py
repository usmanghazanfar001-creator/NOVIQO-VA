"""Password hashing (argon2) and httpOnly-cookie JWT sessions. Sessions are stateless: logout clears the cookie."""
import os, secrets, time
import jwt
from argon2 import PasswordHasher
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from ..database.db import get_db
from ..models.models import User

SECRET = os.getenv("SECRET_KEY") or secrets.token_hex(32)
COOKIE, TTL = "noviqo_session", 7 * 86400
_ph = PasswordHasher()

def hash_pw(p: str) -> str: return _ph.hash(p)
def check_pw(h: str, p: str) -> bool:
    try: return _ph.verify(h, p)
    except Exception: return False

def set_session(resp: Response, uid: str):
    tok = jwt.encode({"sub": uid, "exp": int(time.time()) + TTL}, SECRET, "HS256")
    resp.set_cookie(COOKIE, tok, max_age=TTL, httponly=True, samesite="lax", secure=os.getenv("COOKIE_SECURE") == "true")

async def current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    try: uid = jwt.decode(request.cookies.get(COOKIE), SECRET, algorithms=["HS256"])["sub"]
    except Exception: raise HTTPException(401, "Please log in.")
    user = await db.get(User, uid)
    if not user: raise HTTPException(401, "Please log in.")
    return user
