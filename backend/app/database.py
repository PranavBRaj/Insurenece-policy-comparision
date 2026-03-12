from __future__ import annotations

import logging
import re

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)


def _ensure_database_exists() -> None:
    """Create the database schema if it does not exist yet."""
    url = settings.DATABASE_URL
    # Extract the database name and build a root URL without it
    match = re.match(r"^(mysql\+pymysql://[^/]+/)(\w+)(.*)$", url)
    if not match:
        return  # non-MySQL or unusual URL – skip
    root_url, db_name, extra = match.groups()
    try:
        tmp_engine = create_engine(root_url + extra, isolation_level="AUTOCOMMIT")
        with tmp_engine.connect() as conn:
            conn.execute(text(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            ))
        tmp_engine.dispose()
        logger.info("Database '%s' is ready.", db_name)
    except Exception as exc:
        logger.warning("Could not auto-create database '%s': %s", db_name, exc)


_ensure_database_exists()

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency – yields a DB session and closes it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables() -> None:
    """Create all tables that are defined in db_models and not yet in the DB."""
    # Import models so their metadata is registered on Base
    from app.models import db_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified / created.")


def check_connection() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.error("DB connection check failed: %s", exc)
        return False
