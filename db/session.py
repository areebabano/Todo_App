import logging
import os
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
from sqlmodel import SQLModel, Session

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set")

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_timeout=30,
    connect_args={"sslmode": "require"},
)


def warmup_db():
    """Warm up the database connection pool to avoid cold start delays.

    Call this during application startup to pre-establish connections
    so the first user request doesn't suffer from Neon cold start latency.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            conn.commit()
        logger.info("Database connection warmed up successfully")
    except Exception as exc:
        logger.warning("Database warmup failed (will retry on first request): %s", exc)


def get_session() -> Generator:
    with Session(engine) as session:
        yield session
