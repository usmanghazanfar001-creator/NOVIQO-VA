import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.auth import current_user
from ..core.security import sign, verify
from ..database.db import get_db
from ..models.models import User
from ..services import gcal

router = APIRouter(prefix="/api/calendar")

@router.get("/status")
async def status(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return {"configured": gcal.configured(), "connected": await gcal.connected(db, user.id)}

@router.get("/connect")
async def connect(user: User = Depends(current_user)):
    if not gcal.configured(): raise HTTPException(503, "Google Calendar isn't set up on this server.")
    # `state` is a signed, 10-minute, single-use token bound to this user (CSRF protection for the OAuth flow)
    return RedirectResponse(gcal.auth_url(sign({"name": "gcal_oauth", "input": {}}, user.id, 600)))

@router.get("/callback")
async def callback(code: str | None = None, state: str = "", error: str | None = None,
                   user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    app = os.getenv("APP_URL", "http://localhost:5173")
    try:
        if error or not code: raise ValueError("denied")
        verify(state, user.id)
        await gcal.save(db, user.id, await gcal.exchange_code(code)); await db.commit()
    except ValueError:
        return RedirectResponse(f"{app}/?calendar=error")
    return RedirectResponse(f"{app}/?calendar=connected")

@router.delete("")
async def disconnect(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await gcal.disconnect(db, user.id); await db.commit(); return {"ok": True}
