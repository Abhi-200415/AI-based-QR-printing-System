from enum import Enum
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database.connection import Base
# ==========================
# Job Status
# ==========================

class JobStatus(str, Enum):
    PENDING = "Pending"
    QUEUED = "Queued"
    ASSIGNED = "Assigned"
    PRINTING = "Printing"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


# ==========================
# Payment Status
# ==========================

class PricingBasis(str, Enum):
    PER_SIDE = "PER_SIDE"
    PER_SHEET = "PER_SHEET"

class PaymentStatus(str, Enum):
    PENDING = "Pending"
    PAID = "Paid"
    FAILED = "Failed"
    REFUNDED = "Refunded"


# ==========================
# Printer Status
# ==========================

class PrinterStatus(str, Enum):
    ONLINE = "Online"
    OFFLINE = "Offline"
    BUSY = "Busy"
    MAINTENANCE = "Maintenance"


# ==========================
# Print Type
# ==========================

class PrintType(str, Enum):
    BW = "BW"
    COLOR = "COLOR"
    MIXED = "MIXED"


# ==========================
# Paper Size
# ==========================

class PaperSize(str, Enum):
    A4 = "A4"
    A3 = "A3"
    LETTER = "LETTER"
    LEGAL = "LEGAL"


# ==========================
# Orientation
# ==========================

class Orientation(str, Enum):
    PORTRAIT = "Portrait"
    LANDSCAPE = "Landscape"


# ==========================
# Payment Provider
# ==========================

class PaymentProvider(str, Enum):
    CASHFREE = "Cashfree"
    RAZORPAY = "Razorpay"
    UROPAY = "UroPay"
    MANUAL = "Manual"


# ==========================
# Payment Method
# ==========================

class PaymentMethod(str, Enum):
    UPI = "UPI"
    CARD = "Card"
    CASH = "Cash"
    NETBANKING = "NetBanking"
    WALLET = "Wallet"
# ==========================================
# Shop Owner
# ==========================================

class ShopOwner(Base):
    __tablename__ = "shop_owners"

    owner_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    # Shop Information
    shop_name = Column(String(150), nullable=False)
    owner_name = Column(String(100), nullable=False)
    shop_logo = Column(String(255), nullable=True)

    # Login Information
    email = Column(String(150), unique=True, nullable=False)
    phone = Column(String(20), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)

    # Payment Information
    upi_id = Column(String(100), nullable=True)

    # Address
    address = Column(Text, nullable=True)

    # QR Information
    qr_token = Column(
        String(100),
        unique=True,
        nullable=True
    )

    qr_path = Column(
        String(255),
        nullable=True
    )

    # Account Status
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    # ==========================
    # Relationships
    # ==========================

    settings = relationship(
        "ShopSettings",
        back_populates="owner",
        uselist=False,
        cascade="all, delete-orphan"
    )

    printers = relationship(
        "Printer",
        back_populates="owner",
        cascade="all, delete-orphan"
    )

    pricing_rules = relationship(
        "PricingRule",
        back_populates="owner",
        cascade="all, delete-orphan"
    )

    jobs = relationship(
        "ActiveJob",
        back_populates="owner",
        cascade="all, delete-orphan"
    )

    analytics = relationship(
        "AnalyticsDaily",
        back_populates="owner",
        cascade="all, delete-orphan"
    )
# ==========================================
# Shop Settings
# ==========================================

class ShopSettings(Base):
    __tablename__ = "shop_settings"

    setting_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("shop_owners.owner_id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )

    # Default Printer
    default_printer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("printers.printer_id"),
        nullable=True
    )

    # Currency & Tax
    currency = Column(
        String(10),
        default="INR"
    )

    tax_percentage = Column(
        Numeric(5, 2),
        default=0.00
    )

    # Pricing Basis
    pricing_basis = Column(
        SQLEnum(PricingBasis),
        default=PricingBasis.PER_SIDE,
        nullable=False
    )

    # Printing Options
    allow_bw_print = Column(
        Boolean,
        default=True
    )

    allow_color_print = Column(
        Boolean,
        default=True
    )

    allow_duplex = Column(
        Boolean,
        default=True
    )

    allow_mixed_print = Column(
        Boolean,
        default=True
    )

    allow_page_selection = Column(
        Boolean,
        default=True
    )

    # Upload Settings
    max_file_size_mb = Column(
        Integer,
        default=100
    )

    max_files_per_job = Column(
        Integer,
        default=20
    )

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    # ==========================
    # Relationships
    # ==========================

    owner = relationship(
        "ShopOwner",
        back_populates="settings"
    )

    default_printer = relationship(
        "Printer",
        foreign_keys=[default_printer_id]
    )
# ==========================================
# Printer
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
        ForeignKey(
            "shop_owners.owner_id",
            ondelete="CASCADE"
        ),
        nullable=False
    )

    # ==========================================================
    # Printer Information
    # ==========================================================

    printer_name = Column(
        String(100),
        nullable=False
    )

    printer_model = Column(
        String(100),
        nullable=True
    )

    printer_type = Column(
        String(50),
        nullable=True
    )

    # ==========================================================
    # Physical / Virtual Classification
    # ==========================================================

    is_physical = Column(
        Boolean,
        default=True,
        nullable=False
    )

    is_virtual = Column(
        Boolean,
        default=False,
        nullable=False
    )

    # ==========================================================
    # Availability
    # ==========================================================

    is_available = Column(
        Boolean,
        default=False,
        nullable=False
    )

    # ==========================================================
    # Capabilities
    # ==========================================================

    supports_bw = Column(
        Boolean,
        default=True
    )

    supports_color = Column(
        Boolean,
        default=False
    )

    supports_duplex = Column(
        Boolean,
        default=False
    )

    supports_a3 = Column(
        Boolean,
        default=False
    )

    supports_legal = Column(
        Boolean,
        default=False
    )

    # ==========================================================
    # Status
    # ==========================================================

    status = Column(
        SQLEnum(PrinterStatus),
        default=PrinterStatus.ONLINE,
        nullable=False
    )

    # ==========================================================
    # Agent Information
    # ==========================================================

    agent_id = Column(
        String(100),
        nullable=True
    )

    # ==========================================================
    # Scheduler Information
    # ==========================================================

    current_queue = Column(
        Integer,
        default=0
    )

    total_jobs_printed = Column(
        Integer,
        default=0
    )

    # ==========================================================
    # Monitoring
    # ==========================================================

    last_seen = Column(
        DateTime(timezone=True),
        nullable=True
    )

    # ==========================================================
    # Timestamps
    # ==========================================================

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    # ==========================================================
    # Default Printer
    # ==========================================================

    is_default = Column(
        Boolean,
        default=False
    )

    # ==========================================================
    # Relationships
    # ==========================================================

    owner = relationship(
        "ShopOwner",
        back_populates="printers"
    )

    jobs = relationship(
        "ActiveJob",
        back_populates="assigned_printer"
    )
# ==========================================
# Active Job
# ==========================================

class ActiveJob(Base):
    __tablename__ = "active_jobs"

    job_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("shop_owners.owner_id", ondelete="CASCADE"),
        nullable=False
    )

    assigned_printer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("printers.printer_id"),
        nullable=True
    )

    # Optional Customer Details
    customer_name = Column(
        String(100),
        nullable=True
    )

    customer_phone = Column(
        String(20),
        nullable=True
    )

    # Job Status
    status = Column(
        SQLEnum(JobStatus),
        default=JobStatus.PENDING,
        nullable=False
    )

    # Payment Status
    payment_status = Column(
        SQLEnum(PaymentStatus),
        default=PaymentStatus.PENDING,
        nullable=False
    )

    # Queue Information
    queue_position = Column(
        Integer,
        nullable=True
    )

    priority = Column(
        Integer,
        default=0
    )

    # Job Summary
    total_files = Column(
        Integer,
        default=0
    )

    total_pages = Column(
        Integer,
        default=0
    )

    total_copies = Column(
        Integer,
        default=0
    )

    # Cost
    subtotal = Column(
        Numeric(10, 2),
        default=0
    )

    tax = Column(
        Numeric(10, 2),
        default=0
    )

    total_amount = Column(
        Numeric(10, 2),
        default=0
    )

 # Estimated Printing Time
	
    # Time Tracking
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    queued_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    started_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    completed_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    # ==========================
    # Relationships
    # ==========================

    owner = relationship(
        "ShopOwner",
        back_populates="jobs"
    )

    assigned_printer = relationship(
        "Printer",
        back_populates="jobs"
    )

    files = relationship(
        "JobFile",
        back_populates="job",
        cascade="all, delete-orphan"
    )

    payment = relationship(
        "Payment",
        back_populates="job",
        uselist=False,
        cascade="all, delete-orphan"
    )
# ==========================================
# Job File
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
        ForeignKey("active_jobs.job_id", ondelete="CASCADE"),
        nullable=False
    )

    # ==========================
    # File Information
    # ==========================

    original_filename = Column(
        String(255),
        nullable=False
    )

    stored_filename = Column(
        String(255),
        nullable=False
    )

    file_path = Column(
        Text,
        nullable=False
    )

    file_type = Column(
        String(20),
        nullable=False
    )

    file_size = Column(
        Integer,
        nullable=False
    )

    # ==========================
    # Document Information
    # ==========================

    page_count = Column(
        Integer,
        default=1
    )

    copies = Column(
        Integer,
        default=1
    )

    # ==========================
    # Paper Settings
    # ==========================

    paper_size = Column(
        SQLEnum(PaperSize),
        default=PaperSize.A4
    )

    orientation = Column(
        SQLEnum(Orientation),
        default=Orientation.PORTRAIT
    )

    duplex = Column(
        Boolean,
        default=False
    )

    # ==========================
    # Print Settings
    # ==========================

    print_type = Column(
        SQLEnum(PrintType),
        default=PrintType.BW
    )

    # AUTO / GRAYSCALE / FULL_COLOR
    color_mode = Column(
        String(30),
        default="AUTO"
    )

    # ==========================
    # Page Selection
    # ==========================

    page_ranges = Column(
        String(255),
        nullable=True
    )

    # ==========================
    # Mixed Printing
    # ==========================

    color_page_ranges = Column(
        String(255),
        nullable=True
    )

    bw_pages = Column(
        Integer,
        default=0
    )

    color_pages = Column(
        Integer,
        default=0
    )

    # ==========================
    # AI Information
    # ==========================

    ai_color_detected = Column(
        Boolean,
        default=False
    )

    # ==========================
    # Pricing
    # ==========================

    estimated_cost = Column(
        Numeric(10, 2),
        default=0
    )

    # ==========================
    # Print Status
    # ==========================

    print_completed = Column(
        Boolean,
        default=False
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    # ==========================
    # Relationships
    # ==========================

    job = relationship(
        "ActiveJob",
        back_populates="files"
    )

# ==========================================
# Pricing Rule
# ==========================================

class PricingRule(Base):
    __tablename__ = "pricing_rules"

    pricing_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("shop_owners.owner_id", ondelete="CASCADE"),
        nullable=False
    )

    # ==========================
    # Paper Settings
    # ==========================

    paper_size = Column(
        SQLEnum(PaperSize),
        nullable=False
    )

    print_type = Column(
        SQLEnum(PrintType),
        nullable=False
    )

    duplex = Column(
        Boolean,
        default=False
    )

    # ==========================
    # Page Range
    # ==========================

    page_from = Column(
        Integer,
        nullable=False
    )

    page_to = Column(
        Integer,
        nullable=False
    )

    # ==========================
    # Pricing
    # ==========================

    price_per_page = Column(
        Numeric(10, 2),
        nullable=False
    )

    # ==========================
    # Rule Status
    # ==========================

    is_active = Column(
        Boolean,
        default=True
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    # ==========================
    # Relationships
    # ==========================

    owner = relationship(
        "ShopOwner",
        back_populates="pricing_rules"
    )
# ==========================================
# Payment
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
        ForeignKey("active_jobs.job_id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )

    # ==========================
    # Payment Provider
    # ==========================

    provider = Column(
        SQLEnum(PaymentProvider),
        nullable=False
    )

    payment_method = Column(
        SQLEnum(PaymentMethod),
        default=PaymentMethod.UPI
    )

    # ==========================
    # Payment Information
    # ==========================

    amount = Column(
        Numeric(10, 2),
        nullable=False
    )

    status = Column(
        SQLEnum(PaymentStatus),
        default=PaymentStatus.PENDING,
        nullable=False
    )

    currency = Column(
        String(10),
        default="INR"
    )

    # ==========================
    # Provider References
    # ==========================

    transaction_id = Column(
        String(150),
        nullable=True
    )

    provider_payment_id = Column(
        String(150),
        nullable=True
    )

    qr_reference = Column(
        String(255),
        nullable=True
    )

    # ==========================
    # Verification
    # ==========================

    verified = Column(
        Boolean,
        default=False
    )

    verified_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    # ==========================
    # Time
    # ==========================

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    paid_at = Column(
    DateTime(timezone=True),
    nullable=True
    )

    failure_reason = Column(
        Text,
        nullable=True
    )

    refund_amount = Column(
        Numeric(10, 2),
        default=0
    )

    # ==========================
    # Relationships
    # ==========================

    job = relationship(
        "ActiveJob",
        back_populates="payment"
    )
# ==========================================
# Daily Analytics
# ==========================================

class AnalyticsDaily(Base):
    __tablename__ = "analytics_daily"

    analytics_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("shop_owners.owner_id", ondelete="CASCADE"),
        nullable=False
    )

    # ==========================
    # Analytics Date
    # ==========================

    analytics_date = Column(
        Date,
        nullable=False
    )

    # ==========================
    # Job Statistics
    # ==========================

    total_jobs = Column(
        Integer,
        default=0
    )

    completed_jobs = Column(
        Integer,
        default=0
    )

    failed_jobs = Column(
        Integer,
        default=0
    )

    cancelled_jobs = Column(
        Integer,
        default=0
    )

    # ==========================
    # Printing Statistics
    # ==========================

    total_files = Column(
        Integer,
        default=0
    )

    total_pages = Column(
        Integer,
        default=0
    )

    total_copies = Column(
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

    # ==========================
    # Revenue Statistics
    # ==========================

    total_revenue = Column(
        Numeric(12,2),
        default=0
    )

    total_tax = Column(
        Numeric(12,2),
        default=0
    )

    total_refunds = Column(
        Numeric(12,2),
        default=0
    )

    average_job_value = Column(
        Numeric(10,2),
        default=0
    )

    # ==========================
    # Payment Statistics
    # ==========================

    successful_payments = Column(
        Integer,
        default=0
    )

    failed_payments = Column(
        Integer,
        default=0
    )

    # ==========================
    # Queue Statistics
    # ==========================

    peak_queue_length = Column(
        Integer,
        default=0
    )

    average_wait_time = Column(
        Integer,
        default=0
    )   # Seconds

    # ==========================
    # AI Predictions
    # ==========================

    predicted_jobs = Column(
        Integer,
        default=0
    )

    predicted_pages = Column(
        Integer,
        default=0
    )

    predicted_revenue = Column(
        Numeric(12,2),
        default=0
    )

    predicted_peak_hour = Column(
        Integer,
        nullable=True
    )   # 0-23

    predicted_queue_length = Column(
        Integer,
        default=0
    )

    # ==========================
    # AI Recommendations
    # ==========================

    printer_recommendation = Column(
        Text,
        nullable=True
    )

    pricing_recommendation = Column(
        Text,
        nullable=True
    )

    business_insight = Column(
        Text,
        nullable=True
    )

    # ==========================
    # AI Anomaly Detection
    # ==========================

    anomaly_detected = Column(
        Boolean,
        default=False
    )

    anomaly_reason = Column(
        Text,
        nullable=True
    )

    model_confidence = Column(
        Numeric(5,2),
        default=0
    )

    last_prediction_time = Column(
        DateTime(timezone=True),
        nullable=True
    )

    # ==========================
    # Timestamps
    # ==========================

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    # ==========================
    # Relationships
    # ==========================

    owner = relationship(
        "ShopOwner",
        back_populates="analytics"
    )
    




