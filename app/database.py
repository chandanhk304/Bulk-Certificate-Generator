"""Database engine, session factory and declarative base."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

_is_sqlite = settings.database_url.startswith("sqlite")

# FastAPI runs sync routes/background tasks in a thread pool, so SQLite must allow cross-thread use.
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
)

if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _enable_wal(dbapi_conn, _record):
        # WAL lets status reads proceed while the background worker is writing.
        dbapi_conn.execute("PRAGMA journal_mode=WAL")

# expire_on_commit=False keeps loaded attributes usable after commit (e.g. returning job.id).
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """Parent class for all ORM models."""
