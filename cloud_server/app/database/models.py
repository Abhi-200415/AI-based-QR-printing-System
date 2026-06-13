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


# ==========================================
# SHOP OWNER
# ==========================================

class ShopOwner(Base):
    __tablename__ = "shop_owner"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    shop_name = Column(String(150), nullable=False)

    email = Column(String(255), unique=True, nullable=False)

    password_hash = Column(String, nullable=False)

    upi_id = Column(String(255), nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )


# ==========================================
# SHOP SETTINGS
# ==========================================

class ShopSettings(Base):
    __tablename__ = "shop_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("shop_owner.id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )

    file_delay_seconds = Column(Integer, default=2)

    job_delay_seconds = Column(Integer, default=10)

    auto_delete_minutes = Column(Integer, default=30)

    enable_voice_assistant = Column(Boolean, default=True)

    enable_ai_color_detection = Column(Boolean, default=True)


# ==========================================
# DYNAMIC PRICING
# ==========================================

class PricingRule(Base):
    __tablename__ = "pricing_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("shop_owner.id", ondelete="CASCADE"),
        nullable=False
    )

    rule_name = Column(String(100), nullable=False)

    print_mode = Column(String(20), nullable=False)

    min_pages = Column(Integer, nullable=False)

    max_pages = Column(Integer, nullable=False)

    price_per_page = Column(
        Numeric(10, 2),
        nullable=False
    )

    is_active = Column(Boolean, default=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )


# ==========================================
# PRINTERS
# ==========================================

class Printer(Base):
    __tablename__ = "printers"

    printer_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("shop_owner.id", ondelete="CASCADE"),
        nullable=False
    )

    printer_name = Column(String(100), nullable=False)

    printer_mode = Column(
        String(20),
        nullable=False
    )
    # bw_only
    # color_only
    # color_bw

    pages_per_minute = Column(Integer, default=20)

    status = Column(
        String(20),
        default="offline"
    )
    # offline
    # online
    # busy
    # idle

    current_queue = Column(Integer, default=0)

    last_seen = Column(DateTime(timezone=True))


# ==========================================
# ACTIVE JOBS
# ==========================================

class ActiveJob(Base):
    __tablename__ = "active_jobs"

    job_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    session_id = Column(
        UUID(as_uuid=True),
        nullable=False
    )

    username = Column(String(50))

    assigned_printer_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "printers.printer_id",
            ondelete="SET NULL"
        ),
        nullable=True
    )

    required_printer_type = Column(String(20))

    total_files = Column(Integer, default=0)

    total_pages = Column(Integer, default=0)

    total_amount = Column(
        Numeric(10, 2),
        default=0
    )

    payment_method = Column(
        String(20),
        default="upi"
    )
    # upi
    # cash

    payment_status = Column(
        String(30),
        default="pending"
    )

    print_status = Column(
        String(30),
        default="uploaded"
    )

    queue_position = Column(Integer, default=0)

    estimated_seconds = Column(Integer, default=0)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )


# ==========================================
# JOB FILES
# ==========================================

class JobFile(Base):
    __tablename__ = "job_files"

    file_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "active_jobs.job_id",
            ondelete="CASCADE"
        ),
        nullable=False
    )

    stored_file_name = Column(
        String(255),
        nullable=False
    )

    original_file_name = Column(
        String(255)
    )

    file_type = Column(String(20))

    file_path = Column(String, nullable=False)

    page_count = Column(Integer, default=0)

    copies = Column(Integer, default=1)

    print_mode = Column(
        String(20),
        default="bw"
    )

    duplex = Column(
        Boolean,
        default=False
    )

    ai_color_detected = Column(
        Boolean,
        default=False
    )

    detected_color_pages = Column(
        Integer,
        default=0
    )

    estimated_print_cost = Column(
        Numeric(10, 2),
        default=0
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )


# ==========================================
# PAYMENTS
# ==========================================

class Payment(Base):
    __tablename__ = "payments"

    payment_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "active_jobs.job_id",
            ondelete="CASCADE"
        ),
        nullable=False
    )

    amount = Column(
        Numeric(10, 2),
        nullable=False
    )

    payment_method = Column(String(20))

    provider_order_id = Column(String(255))

    payment_status = Column(
        String(30),
        default="pending"
    )

    paid_at = Column(
        DateTime(timezone=True)
    )


# ==========================================
# DAILY ANALYTICS
# ==========================================

class AnalyticsDaily(Base):
    __tablename__ = "analytics_daily"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "shop_owner.id",
            ondelete="CASCADE"
        ),
        nullable=False
    )

    analytics_date = Column(
        DateTime(timezone=True)
    )

    total_jobs = Column(
        Integer,
        default=0
    )

    total_pages = Column(
        Integer,
        default=0
    )

    bw_pages = Column(
        Integer,
        default=0
    )

    color_pages = Column(
        Integer,
        default=0
    )

    revenue = Column(
        Numeric(12, 2),
        default=0
    )