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

    if os.getenv("TESTING", "").lower() in ("true", "1") or not db_url or db_url.startswith("sqlite"):
        return create_engine(
            sqlite_url,
            connect_args={"check_same_thread": False},
            pool_pre_ping=True
        )

    try:
        connect_args = {}
        if "postgres" in db_url:
            connect_args["connect_timeout"] = 4

        eng = create_engine(
            db_url,
            pool_pre_ping=True,
            connect_args=connect_args,
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
    """Create all database tables on application startup and verify columns."""
    try:
        from app.database import models  # noqa: F401
        logger.info("Verifying database schema...")
        Base.metadata.create_all(bind=engine)

        is_postgres = "postgres" in str(engine.url)
        with engine.begin() as conn:
            if is_postgres:
                conn.execute(text("SET lock_timeout = '3s'"))

            alter_statements = [
                "ALTER TABLE active_jobs ADD COLUMN IF NOT EXISTS customer_reference VARCHAR(100)",
                "ALTER TABLE active_jobs ADD COLUMN IF NOT EXISTS finishing_status VARCHAR(30) DEFAULT 'NONE'",
                "ALTER TABLE active_jobs ADD COLUMN IF NOT EXISTS finishing_completed_at TIMESTAMP WITH TIME ZONE",
                "ALTER TABLE job_finishing_services ADD COLUMN IF NOT EXISTS file_id UUID REFERENCES job_files(file_id) ON DELETE CASCADE",
                "ALTER TABLE job_files ADD COLUMN IF NOT EXISTS assigned_printer_id UUID REFERENCES printers(printer_id) ON DELETE SET NULL",
                "ALTER TABLE job_files ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'Pending'",
                "ALTER TABLE job_files ADD COLUMN IF NOT EXISTS started_at TIMESTAMP WITH TIME ZONE",
                "ALTER TABLE job_files ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP WITH TIME ZONE"
            ] if is_postgres else [
                "ALTER TABLE active_jobs ADD COLUMN customer_reference VARCHAR(100)",
                "ALTER TABLE active_jobs ADD COLUMN finishing_status VARCHAR(30) DEFAULT 'NONE'",
                "ALTER TABLE active_jobs ADD COLUMN finishing_completed_at TIMESTAMP WITH TIME ZONE",
                "ALTER TABLE job_finishing_services ADD COLUMN file_id UUID REFERENCES job_files(file_id) ON DELETE CASCADE",
                "ALTER TABLE job_files ADD COLUMN assigned_printer_id UUID REFERENCES printers(printer_id) ON DELETE SET NULL",
                "ALTER TABLE job_files ADD COLUMN status VARCHAR(20) DEFAULT 'Pending'",
                "ALTER TABLE job_files ADD COLUMN started_at TIMESTAMP WITH TIME ZONE",
                "ALTER TABLE job_files ADD COLUMN completed_at TIMESTAMP WITH TIME ZONE"
            ]

            for stmt in alter_statements:
                try:
                    conn.execute(text(stmt))
                except Exception:
                    pass

        logger.info("Database schema initialized and tables verified.")
    except Exception as e:
        logger.error(f"Error initializing database schema: {e}")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()