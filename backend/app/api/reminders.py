from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.auth import current_user
from ..database.db import get_db
from ..models.models import Reminder, User, _now

router = APIRouter(prefix="/api/reminders")
out = lambda r: {"id": r.id, "text": r.text, "due_at": r.due_at.isoformat() + "Z"}

@router.get("")
async def upcoming(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(select(Reminder).where(Reminder.user_id == user.id, Reminder.delivered == False).order_by(Reminder.due_at))  # noqa: E712
    return [out(r) for r in rows]

@router.get("/due")
async def due(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """Returns reminders whose time has come and marks them delivered (the client polls this while open)."""
    rows = (await db.scalars(select(Reminder).where(Reminder.user_id == user.id, Reminder.delivered == False,  # noqa: E712
                                                    Reminder.due_at <= _now()).order_by(Reminder.due_at))).all()
    for r in rows: r.delivered = True
    await db.commit(); return [out(r) for r in rows]

@router.delete("/{rid}")
async def cancel(rid: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    r = await db.execute(delete(Reminder).where(Reminder.id == rid, Reminder.user_id == user.id, Reminder.delivered == False))  # noqa: E712
    await db.commit()
    if not r.rowcount: raise HTTPException(404, "Reminder not found.")
    return {"ok": True}
