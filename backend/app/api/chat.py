import json, logging
from typing import Literal
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..agents.agent import confirm_call, run, run_stream
from ..ai.llm import LLMError, get_provider
from ..core.auth import current_user
from ..core.limits import limiter
from ..core.security import verify
from ..database.db import SessionLocal, get_db
from ..models.models import Conversation, Memory, Message, User, _now
from .data import get_settings, owned

log = logging.getLogger("noviqo.chat")
router = APIRouter(prefix="/api")

class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = Field(default=None, max_length=32)
    via: Literal["voice", "text"] = "text"
    tz: str | None = Field(default=None, max_length=64)

class ConfirmIn(BaseModel):
    token: str = Field(max_length=4000)
    tz: str | None = Field(default=None, max_length=64)

async def _prepare(db, user, body):
    if body.conversation_id: conv = await owned(db, user, body.conversation_id)
    else:
        conv = Conversation(user_id=user.id, title=body.message[:40]); db.add(conv); await db.flush()
    hist = (await db.scalars(select(Message).where(Message.conversation_id == conv.id).order_by(Message.id.desc()).limit(20))).all()[::-1]
    msgs = [{"role": m.role, "content": m.content} for m in hist] + [{"role": "user", "content": body.message}]
    mems = None
    if (await get_settings(db, user.id))["memory_enabled"]:
        mems = list(await db.scalars(select(Memory.text).where(Memory.user_id == user.id).order_by(Memory.id)))
    return conv, msgs, mems

@router.post("/chat")
@limiter.limit("30/minute")
async def chat(request: Request, body: ChatIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    conv, msgs, mems = await _prepare(db, user, body)
    try:
        reply, actions, pending = await run(get_provider(), msgs, body.tz, mems, db=db, user_id=user.id, email=user.email)
    except LLMError as e:
        await db.rollback(); return JSONResponse({"error": str(e)}, 502)
    except Exception:
        log.exception("chat failed"); await db.rollback()  # details stay in server logs only
        return JSONResponse({"error": "Something went wrong on the server."}, 500)
    db.add_all([Message(conversation_id=conv.id, role="user", content=body.message, via=body.via),
                Message(conversation_id=conv.id, role="assistant", content=reply, via=body.via)])
    conv.updated_at = _now(); await db.commit()
    return {"conversation_id": conv.id, "title": conv.title, "reply": reply, "actions": actions, "pending": pending}

@router.post("/confirm")
@limiter.limit("30/minute")
async def confirm(request: Request, body: ConfirmIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """Runs a tool call the user approved. Only server-signed, unexpired, unused tokens issued to this user are accepted."""
    try: out, actions = await confirm_call(verify(body.token, user.id), body.tz, db, user.id, user.email)
    except ValueError as e: return JSONResponse({"error": str(e)}, 400)
    if "error" in out:
        await db.rollback(); return JSONResponse({"error": f"I couldn't do that: {out['error']}."}, 400)
    await db.commit(); return {"reply": "Done.", "actions": actions}

def _ev(name: str, data: dict) -> str: return f"event: {name}\ndata: {json.dumps(data)}\n\n"

@router.post("/chat/stream")
@limiter.limit("30/minute")
async def chat_stream(request: Request, body: ChatIn, user: User = Depends(current_user)):
    """Server-sent events: `delta` (text as it is written), `reset` (a tool round began), then `done` or `error`."""
    db = SessionLocal()   # own session: it must outlive the request handler while the response streams
    try: conv, msgs, mems = await _prepare(db, user, body)
    except BaseException:
        await db.close(); raise

    async def events():
        try:
            async for kind, v in run_stream(get_provider(), msgs, body.tz, mems, db=db, user_id=user.id, email=user.email):
                if kind == "delta": yield _ev("delta", {"text": v})
                elif kind == "reset": yield _ev("reset", {})
                else: reply, actions, pending = v
            db.add_all([Message(conversation_id=conv.id, role="user", content=body.message, via=body.via),
                        Message(conversation_id=conv.id, role="assistant", content=reply, via=body.via)])
            conv.updated_at = _now(); await db.commit()
            yield _ev("done", {"conversation_id": conv.id, "title": conv.title, "reply": reply, "actions": actions, "pending": pending})
        except LLMError as e:
            await db.rollback(); yield _ev("error", {"error": str(e)})
        except Exception:
            log.exception("chat stream failed"); await db.rollback(); yield _ev("error", {"error": "Something went wrong on the server."})
        finally:
            await db.close()
    return StreamingResponse(events(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"})
