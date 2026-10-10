"""Per-user data. Every query is filtered by the authenticated user's id; foreign ids behave as 404."""
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.auth import COOKIE, check_pw, current_user
from ..database.db import get_db
from ..services import gcal
from ..models.models import Conversation, Memory, Message, Note, PasswordReset, Reminder, User, UserSettings

router = APIRouter(prefix="/api")
Db, Me = Depends(get_db), Depends(current_user)

async def owned(db: AsyncSession, user: User, cid: str) -> Conversation:
    c = await db.scalar(select(Conversation).where(Conversation.id == cid, Conversation.user_id == user.id))
    if not c: raise HTTPException(404, "Conversation not found.")
    return c

class Title(BaseModel): title: str = Field(min_length=1, max_length=60)
class Text(BaseModel): text: str = Field(min_length=1, max_length=2000)

# ----- conversations -----
@router.get("/conversations")
async def list_conversations(q: str = Query("", max_length=100), user: User = Me, db: AsyncSession = Db):
    stmt = select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.updated_at.desc())
    if q:
        ql = q.lower()
        hit = select(Message.conversation_id).where(func.lower(Message.content).contains(ql, autoescape=True))
        stmt = stmt.where(or_(func.lower(Conversation.title).contains(ql, autoescape=True), Conversation.id.in_(hit)))
    convs = (await db.scalars(stmt.limit(200))).all()
    voice = set(await db.scalars(select(Message.conversation_id).where(
        Message.via == "voice", Message.conversation_id.in_([c.id for c in convs])).distinct()))
    return [{"id": c.id, "title": c.title, "updated_at": c.updated_at.isoformat() + "Z",
             "via": "voice" if c.id in voice else "text"} for c in convs]

@router.post("/conversations")
async def create_conversation(body: Title, user: User = Me, db: AsyncSession = Db):
    c = Conversation(user_id=user.id, title=body.title); db.add(c); await db.commit()
    return {"id": c.id, "title": c.title}

@router.get("/conversations/{cid}")
async def get_conversation(cid: str, user: User = Me, db: AsyncSession = Db):
    c = await owned(db, user, cid)
    msgs = await db.scalars(select(Message).where(Message.conversation_id == cid).order_by(Message.id))
    return {"id": c.id, "title": c.title, "messages": [{"role": m.role, "content": m.content, "via": m.via} for m in msgs]}

@router.patch("/conversations/{cid}")
async def rename_conversation(cid: str, body: Title, user: User = Me, db: AsyncSession = Db):
    c = await owned(db, user, cid); c.title = body.title; await db.commit(); return {"id": c.id, "title": c.title}

@router.delete("/conversations/{cid}")
async def delete_conversation(cid: str, user: User = Me, db: AsyncSession = Db):
    c = await owned(db, user, cid)
    await db.execute(delete(Message).where(Message.conversation_id == cid)); await db.delete(c); await db.commit()
    return {"ok": True}

# ----- notes & memories -----
@router.get("/notes")
async def list_notes(user: User = Me, db: AsyncSession = Db):
    return [{"id": n.id, "text": n.text} for n in await db.scalars(select(Note).where(Note.user_id == user.id).order_by(Note.id))]

@router.post("/notes")
async def create_note(body: Text, user: User = Me, db: AsyncSession = Db):
    n = Note(user_id=user.id, text=body.text); db.add(n); await db.commit(); return {"id": n.id, "text": n.text}

@router.delete("/notes/{nid}")
async def delete_note(nid: int, user: User = Me, db: AsyncSession = Db):
    r = await db.execute(delete(Note).where(Note.id == nid, Note.user_id == user.id)); await db.commit()
    if not r.rowcount: raise HTTPException(404, "Note not found.")
    return {"ok": True}

@router.get("/memories")
async def list_memories(user: User = Me, db: AsyncSession = Db):
    return [{"id": m.id, "text": m.text} for m in await db.scalars(select(Memory).where(Memory.user_id == user.id).order_by(Memory.id))]

@router.post("/memories")
async def create_memory(body: Text, user: User = Me, db: AsyncSession = Db):
    if len(body.text) > 200: raise HTTPException(422, "Memories are limited to 200 characters.")
    if await db.scalar(select(func.count()).select_from(Memory).where(Memory.user_id == user.id)) >= 20:
        raise HTTPException(409, "Memory is full. Delete something first.")
    m = Memory(user_id=user.id, text=body.text); db.add(m); await db.commit(); return {"id": m.id, "text": m.text}

@router.delete("/memories/{mid}")
async def delete_memory(mid: int, user: User = Me, db: AsyncSession = Db):
    r = await db.execute(delete(Memory).where(Memory.id == mid, Memory.user_id == user.id)); await db.commit()
    if not r.rowcount: raise HTTPException(404, "Memory not found.")
    return {"ok": True}

@router.delete("/memories")
async def clear_memories(user: User = Me, db: AsyncSession = Db):
    await db.execute(delete(Memory).where(Memory.user_id == user.id)); await db.commit(); return {"ok": True}

# ----- settings -----
class Settings(BaseModel):
    memory_enabled: bool = True
    auto_speak: bool = True
    speech_rate: float = Field(1.0, ge=0.5, le=2.0)
    voice: str | None = Field(None, max_length=200)
    theme: Literal["dark", "light", "system"] = "dark"

async def get_settings(db: AsyncSession, uid: str) -> dict:
    row = await db.get(UserSettings, uid)
    return Settings(**(row.data if row else {})).model_dump()

@router.get("/settings")
async def read_settings(user: User = Me, db: AsyncSession = Db): return await get_settings(db, user.id)

@router.put("/settings")
async def write_settings(body: Settings, user: User = Me, db: AsyncSession = Db):
    row, data = await db.get(UserSettings, user.id), body.model_dump()
    if row: row.data = data
    else: db.add(UserSettings(user_id=user.id, data=data))
    await db.commit(); return data

# ----- privacy -----
async def wipe(db: AsyncSession, uid: str):
    await gcal.disconnect(db, uid)   # revoke Google's grant, then forget the token
    mine = select(Conversation.id).where(Conversation.user_id == uid)
    await db.execute(delete(Message).where(Message.conversation_id.in_(mine)))
    for m in (Conversation, Note, Memory, Reminder, UserSettings): await db.execute(delete(m).where(m.user_id == uid))

@router.delete("/me/data")
async def delete_all_data(user: User = Me, db: AsyncSession = Db):
    await wipe(db, user.id); await db.commit(); return {"ok": True}

class PasswordIn(BaseModel): password: str = Field(max_length=128)

@router.post("/me/delete")  # POST with password confirmation: permanently removes the account
async def delete_account(body: PasswordIn, response: Response, user: User = Me, db: AsyncSession = Db):
    if not check_pw(user.password_hash, body.password): raise HTTPException(403, "Incorrect password.")
    await wipe(db, user.id); await db.execute(delete(PasswordReset).where(PasswordReset.user_id == user.id))
    await db.delete(user); await db.commit(); response.delete_cookie(COOKIE); return {"ok": True}
