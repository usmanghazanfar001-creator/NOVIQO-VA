import os
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./noviqo.db")
engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase): pass

async def get_db():
    async with SessionLocal() as s: yield s

async def init_db():  # create_all is idempotent; add Alembic when the schema starts changing
    from ..models import models  # noqa: F401
    async with engine.begin() as c: await c.run_sync(Base.metadata.create_all)
