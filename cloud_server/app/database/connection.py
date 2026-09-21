import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from pathlib import Path
from app.core.config import DATABASE_URL, BASE_DIR

logger = logging.getLogger("cloud_server.database")
Base = declarative_base()


def create_db_engine(db_url: str):
    """
    Creates the database engine with connection pooling.
    If the primary database (e.g. remote PostgreSQL) is unreachable,
    gracefully falls back to local SQLite to ensure uninterrupted service.
    """
    sqlite_path = Path(BASE_DIR) / "ai_printing.db"
    sqlite_url = f"sqlite:///{sqlite_path.as_posix()}"

    if not db_url or db_url.startswith("sqlite"):
        return create_engine(
            sqlite_url,
            connect_args={"check_same_thread": False},
            pool_pre_ping=True
        )

    try:
        eng = create_engine(
            db_url,
            pool_pre_ping=True,
            pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
            max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
            pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "1800"))
        )
        # Test connection validity immediately
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Connected to primary PostgreSQL database.")
        return eng
    except Exception as e:
        logger.warning(
            f"Unable to connect to primary database ({DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}): {e}. "
            f"Falling back to local persistent SQLite ({sqlite_url}) for high availability."
        )
        return create_engine(
            sqlite_url,
            connect_args={"check_same_thread": False},
            pool_pre_ping=True
        )



engine = create_db_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def init_db():
    """Create all database tables on application startup."""
    try:
        from app.database import models  # noqa: F401
        Base.metadata.create_all(bind=engine)
        logger.info("Database schema initialized and tables verified.")
    except Exception as e:
        logger.error(f"Error initializing database schema: {e}")


# Initialize tables immediately upon engine creation
init_db()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()