from functools import lru_cache

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import get_settings


def _sqlite_connect_args() -> dict:
    """Allow FastAPI thread pool + wait on busy lock (default sqlite3 timeout is ~5s)."""
    return {
        "check_same_thread": False,
        "timeout": 30.0,
    }


def _apply_sqlite_pragmas(dbapi_conn, _connection_record) -> None:
    """WAL + busy_timeout reduce OperationalError: database is locked under concurrent writes."""
    cursor = dbapi_conn.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")
    finally:
        cursor.close()


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    settings = get_settings()
    url = settings.db_url
    if url.startswith("sqlite"):
        engine = create_engine(
            url,
            future=True,
            pool_pre_ping=True,
            poolclass=NullPool,
            connect_args=_sqlite_connect_args(),
        )
        event.listen(engine, "connect", _apply_sqlite_pragmas)
        return engine
    return create_engine(url, future=True, pool_pre_ping=True)


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, class_=Session)
