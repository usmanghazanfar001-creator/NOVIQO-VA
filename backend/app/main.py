import os
from dotenv import load_dotenv
load_dotenv()  # before importing modules that read DATABASE_URL / SECRET_KEY

import asyncio  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402
from fastapi import FastAPI, Request  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from slowapi.errors import RateLimitExceeded  # noqa: E402
from starlette.exceptions import HTTPException as HTTPError  # noqa: E402
from .api import auth, calendar, chat, data, reminders  # noqa: E402
from .services.email import smtp_configured  # noqa: E402
from .services.reminders import mail_loop  # noqa: E402
from .core.limits import limiter  # noqa: E402
from .core.config import check_production  # noqa: E402
from .core.observability import init_sentry, install, setup_logging  # noqa: E402
from .database.db import SessionLocal, init_db  # noqa: E402
from sqlalchemy import text  # noqa: E402

PROD = os.getenv("ENV") == "production"
setup_logging(); init_sentry()

@asynccontextmanager
async def lifespan(_: FastAPI):
    if PROD: check_production()   # fail fast on unsafe settings
    await init_db()
    task = asyncio.create_task(mail_loop()) if smtp_configured() else None   # emails overdue reminders
    yield
    if task: task.cancel()

app = FastAPI(title="NOVIQO API", lifespan=lifespan, redoc_url=None,
              docs_url=None if PROD else "/docs", openapi_url=None if PROD else "/openapi.json")
install(app)
app.state.limiter = limiter
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
                   allow_credentials=True, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["Content-Type"])
for r in (auth.router, chat.router, data.router, reminders.router, calendar.router): app.include_router(r)

# every error reaches the client as {"error": "<readable message>"}
@app.exception_handler(RateLimitExceeded)
async def _rl(_: Request, __): return JSONResponse({"error": "Too many requests. Slow down a moment."}, 429)
@app.exception_handler(HTTPError)
async def _http(_: Request, e: HTTPError): return JSONResponse({"error": e.detail}, e.status_code)
@app.exception_handler(RequestValidationError)
async def _val(_: Request, __): return JSONResponse({"error": "Please check what you entered and try again."}, 422)

@app.get("/api/health")
def health(): return {"ok": True}

@app.get("/api/ready")
async def ready():
    """Readiness: can we reach the database? (/api/health is liveness only.)"""
    try:
        async with SessionLocal() as db: await db.execute(text("SELECT 1"))
    except Exception: return JSONResponse({"error": "database unavailable"}, 503)
    return {"ok": True}
