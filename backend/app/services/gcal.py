"""Google Calendar via OAuth. Scope is calendar.events only. Refresh tokens are stored encrypted (key derived from
SECRET_KEY, so SECRET_KEY must be stable). Event text from Google is untrusted: only title/time/location are returned."""
import base64, hashlib, os
from urllib.parse import urlencode
import httpx
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.auth import SECRET
from ..models.models import CalendarAccount

AUTH_URL, TOKEN_URL, REVOKE_URL = "https://accounts.google.com/o/oauth2/v2/auth", "https://oauth2.googleapis.com/token", "https://oauth2.googleapis.com/revoke"
API = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
SCOPE = "https://www.googleapis.com/auth/calendar.events"
_f = lambda: Fernet(base64.urlsafe_b64encode(hashlib.sha256(SECRET.encode()).digest()))
_cid, _sec = lambda: os.getenv("GOOGLE_CLIENT_ID", ""), lambda: os.getenv("GOOGLE_CLIENT_SECRET", "")
redirect_uri = lambda: os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:5173/api/calendar/callback")

def configured() -> bool: return bool(_cid() and _sec())

def auth_url(state: str) -> str:
    return AUTH_URL + "?" + urlencode({"client_id": _cid(), "redirect_uri": redirect_uri(), "response_type": "code", "scope": SCOPE,
                                       "access_type": "offline", "prompt": "consent", "state": state})

async def _http(method: str, url: str, **kw) -> dict:   # the single network seam (tests replace it)
    try:
        async with httpx.AsyncClient(timeout=15) as c: r = await c.request(method, url, **kw)
    except httpx.HTTPError: raise ValueError("couldn't reach Google Calendar")
    if r.status_code >= 400: raise ValueError("Google Calendar rejected the request")
    return r.json() if r.content else {}

async def exchange_code(code: str) -> str:
    d = await _http("POST", TOKEN_URL, data={"code": code, "client_id": _cid(), "client_secret": _sec(),
                                             "redirect_uri": redirect_uri(), "grant_type": "authorization_code"})
    if not d.get("refresh_token"): raise ValueError("Google didn't return a refresh token")
    return d["refresh_token"]

async def save(db: AsyncSession, uid: str, refresh: str):
    enc, row = _f().encrypt(refresh.encode()).decode(), await db.get(CalendarAccount, uid)
    if row: row.refresh_token = enc
    else: db.add(CalendarAccount(user_id=uid, refresh_token=enc))

async def connected(db: AsyncSession, uid: str) -> bool: return await db.get(CalendarAccount, uid) is not None

async def disconnect(db: AsyncSession, uid: str):
    row = await db.get(CalendarAccount, uid)
    if not row: return
    try: await _http("POST", REVOKE_URL, params={"token": _f().decrypt(row.refresh_token.encode()).decode()})  # best effort
    except Exception: pass
    await db.delete(row)

async def _headers(db: AsyncSession, uid: str) -> dict:
    row = await db.get(CalendarAccount, uid)
    if not row: raise ValueError("Google Calendar isn't connected. Connect it in Settings.")
    try: rt = _f().decrypt(row.refresh_token.encode()).decode()
    except Exception: raise ValueError("Google Calendar needs to be reconnected in Settings.")
    d = await _http("POST", TOKEN_URL, data={"refresh_token": rt, "client_id": _cid(), "client_secret": _sec(), "grant_type": "refresh_token"})
    return {"Authorization": f"Bearer {d['access_token']}"}

async def list_events(db, uid, start_utc: str, end_utc: str) -> list[dict]:
    d = await _http("GET", API, headers=await _headers(db, uid), params={"timeMin": start_utc, "timeMax": end_utc,
                    "singleEvents": "true", "orderBy": "startTime", "maxResults": 20})
    return [{"title": (e.get("summary") or "(no title)")[:100], "start": e["start"].get("dateTime") or e["start"].get("date"),
             "end": e["end"].get("dateTime") or e["end"].get("date"), "location": (e.get("location") or "")[:100]} for e in d.get("items", [])]

async def add_event(db, uid, title: str, start_iso: str, end_iso: str, tz: str) -> str | None:
    # no attendees field on purpose: adding guests would send invitations to other people
    d = await _http("POST", API, headers=await _headers(db, uid),
                    json={"summary": title, "start": {"dateTime": start_iso, "timeZone": tz}, "end": {"dateTime": end_iso, "timeZone": tz}})
    return d.get("htmlLink")
