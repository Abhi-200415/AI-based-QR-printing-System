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
    """Create all database tables on application startup and verify columns."""
    try:
        from app.database import models  # noqa: F401
        Base.metadata.create_all(bind=engine)

        with engine.connect() as conn:
            # Create finishing tables if not exist
            try:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS finishing_services (
                        service_id UUID PRIMARY KEY,
                        owner_id UUID NOT NULL REFERENCES shop_owners(owner_id) ON DELETE CASCADE,
                        service_name VARCHAR(100) NOT NULL,
                        description VARCHAR(255),
                        price NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
                        charge_type VARCHAR(50) NOT NULL DEFAULT 'PER_ORDER',
                        is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    )
                """))
            except Exception:
                pass

            try:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS job_finishing_services (
                        id UUID PRIMARY KEY,
                        job_id UUID NOT NULL REFERENCES active_jobs(job_id) ON DELETE CASCADE,
                        service_id UUID REFERENCES finishing_services(service_id) ON DELETE SET NULL,
                        service_name VARCHAR(100) NOT NULL,
                        unit_price NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
                        quantity INTEGER NOT NULL DEFAULT 1,
                        total_price NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    )
                """))
            except Exception:
                pass

        for alter_stmt in [
            "ALTER TABLE active_jobs ADD COLUMN customer_reference VARCHAR(100)",
            "ALTER TABLE active_jobs ADD COLUMN finishing_status VARCHAR(30) DEFAULT 'NONE'",
            "ALTER TABLE active_jobs ADD COLUMN finishing_completed_at TIMESTAMP WITH TIME ZONE",
            "ALTER TABLE job_finishing_services ADD COLUMN file_id UUID REFERENCES job_files(file_id) ON DELETE CASCADE"
        ]:
            try:
                with engine.begin() as conn:
                    conn.execute(text(alter_stmt))
            except Exception:
                pass

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