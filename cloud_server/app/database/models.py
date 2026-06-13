from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    DateTime,
    Numeric,
    ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.database.connection import Base


class ShopOwner(Base):
    __tablename__ = "shop_owner"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    shop_name = Column(String(150), nullable=False)
    owner_name = Column(String(100))
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    upi_id = Column(String(255), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ShopSettings(Base):
    __tablename__ = "shop_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("shop_owner.id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )

    bw_price = Column(Numeric(10, 2), default=2.00)
    color_price = Column(Numeric(10, 2), default=5.00)
    duplex_price = Column(Numeric(10, 2), default=0.00)

    file_delay_seconds = Column(Integer, default=2)
    job_delay_seconds = Column(Integer, default=10)


class ActiveJob(Base):
    __tablename__ = "active_jobs"

    job_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    session_id = Column(UUID(as_uuid=True), nullable=False)

    username = Column(String(50))

    total_files = Column(Integer, default=0)
    total_pages = Column(Integer, default=0)

    total_amount = Column(Numeric(10, 2), default=0)

    payment_status = Column(String(20), default="pending")
    print_status = Column(String(20), default="uploaded")

    queue_position = Column(Integer, default=0)
    estimated_seconds = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class JobFile(Base):
    __tablename__ = "job_files"

    file_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("active_jobs.job_id", ondelete="CASCADE"),
        nullable=False
    )

    file_name = Column(String(255), nullable=False)

    file_path = Column(String, nullable=False)

    page_count = Column(Integer, default=0)

    copies = Column(Integer, default=1)

    print_mode = Column(String(20), default="bw")

    duplex = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())