"""SMTP email (STARTTLS). Unconfigured -> the message is logged (dev) instead of sent."""
import asyncio, logging, os, smtplib
from email.message import EmailMessage

log = logging.getLogger("noviqo.email")
_tasks: set = set()

def smtp_configured() -> bool: return bool(os.getenv("SMTP_HOST"))

def _send(msg: EmailMessage):
    with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.getenv("SMTP_PORT", "587")), timeout=15) as s:
        s.starttls()
        if os.getenv("SMTP_USER"): s.login(os.environ["SMTP_USER"], os.getenv("SMTP_PASSWORD", ""))
        s.send_message(msg)

async def send_email(to: str, subject: str, body: str) -> bool:
    subject = " ".join(subject.split())[:150]   # no newlines in headers
    if not smtp_configured():
        log.warning("[dev email] to=%s subject=%s\n%s", to, subject, body); return False
    m = EmailMessage(); m["To"], m["Subject"] = to, subject
    m["From"] = os.getenv("SMTP_FROM") or os.getenv("SMTP_USER") or "noviqo@localhost"
    m.set_content(body)
    try: await asyncio.to_thread(_send, m); return True
    except Exception: log.exception("email failed"); return False

def fire_and_forget(coro):
    t = asyncio.get_running_loop().create_task(coro); _tasks.add(t); t.add_done_callback(_tasks.discard)
