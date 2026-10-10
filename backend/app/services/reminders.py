"""Overdue reminders (user wasn't in the app within 90 s) are emailed. Run in ONE worker only."""
import asyncio, logging
from datetime import timedelta
from sqlalchemy import select
from ..database.db import SessionLocal
from ..models.models import Reminder, User, _now
from .email import send_email

log = logging.getLogger("noviqo.reminders")

async def mail_due() -> int:
    async with SessionLocal() as db:
        rows = (await db.execute(select(Reminder, User.email).join(User, User.id == Reminder.user_id)
                .where(Reminder.delivered == False, Reminder.due_at <= _now() - timedelta(seconds=90)))).all()  # noqa: E712
        for r, email in rows:
            r.delivered = True
            await send_email(email, f"Reminder: {r.text[:60]}", r.text)
        await db.commit(); return len(rows)

async def mail_loop():
    while True:
        await asyncio.sleep(30)
        try: await mail_due()
        except Exception: log.exception("reminder mailer failed")
