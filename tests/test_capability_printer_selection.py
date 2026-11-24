import uuid
import pytest
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.connection import Base
from app.database.models import (
    ShopOwner,
    Printer,
    PrinterStatus,
    ActiveJob,
    JobFile,
    PrintType,
    PaperSize,
    Orientation,
    JobStatus,
    PaymentStatus
)
from app.services.assignment_service import (
    is_printer_eligible_for_file,
    is_printer_eligible,
    calculate_printer_affinity_tier,
    calculate_printer_selection_score,
    assign_printer
)


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()

    yield session

    session.close()


def test_bw_job_prefers_dedicated_monochrome_printer(db_session):
    """
    CRITICAL BUG TEST: When customer selects B/W, system must prefer a dedicated
    monochrome printer (HP LaserJet) over an equally available color printer (Epson).
    """
    owner_id = uuid.uuid4()
    owner = ShopOwner(
        owner_id=owner_id,
        owner_name="Test Owner",
        shop_name="Test Print Shop",
        email="test@shop.com",
        phone="9999999999",
        password_hash="hash",
        is_active=True
    )
    db_session.add(owner)

    # 1. Dedicated Monochrome Printer (e.g. HP LaserJet)
    hp_mono = Printer(
        printer_id=uuid.uuid4(),
        owner_id=owner_id,
        printer_name="HP LaserJet Pro MFP M126",
        supports_bw=True,
        supports_color=False,
        supports_duplex=False,
        supports_a3=False,
        supports_legal=True,
        status=PrinterStatus.ONLINE,
        is_available=True,
        current_queue=0,
        total_jobs_printed=10
    )

    # 2. Colour Multi-Function Printer (e.g. Epson Universal)
    epson_color = Printer(
        printer_id=uuid.uuid4(),
        owner_id=owner_id,
        printer_name="Epson Universal Print Driver",
        supports_bw=True,
        supports_color=True,
        supports_duplex=True,
        supports_a3=False,
        supports_legal=True,
        status=PrinterStatus.ONLINE,
        is_available=True,
        current_queue=0,
        total_jobs_printed=10
    )

    db_session.add_all([hp_mono, epson_color])
    db_session.commit()

    # Create Black and White customer job
    job = ActiveJob(
        job_id=uuid.uuid4(),
        owner_id=owner_id,
        customer_name="Alice B/W Customer",
        status=JobStatus.PENDING,
        payment_status=PaymentStatus.PAID,
        total_files=1,
        total_pages=5
    )
    db_session.add(job)
    db_session.commit()

    file1 = JobFile(
        file_id=uuid.uuid4(),
        job_id=job.job_id,
        original_filename="Lecture_Notes.pdf",
        print_type=PrintType.BW,
        paper_size=PaperSize.A4,
        duplex=False,
        page_count=5,
        copies=1
    )
    db_session.add(file1)
    db_session.commit()

    # Execute printer assignment
    selected_printer = assign_printer(job, db_session)

    assert selected_printer is not None
    # Dedicated monochrome printer MUST be selected over color printer
    assert selected_printer.printer_id == hp_mono.printer_id
    assert selected_printer.printer_name == "HP LaserJet Pro MFP M126"
    assert job.assigned_printer_id == hp_mono.printer_id


def test_bw_job_falls_back_to_color_printer_when_no_mono_available(db_session):
    """
    If only a color printer is available/online, B/W jobs must safely route to it as fallback.
    """
    owner_id = uuid.uuid4()
    owner = ShopOwner(
        owner_id=owner_id,
        owner_name="Test Owner",
        shop_name="Color-Only Shop",
        email="color@shop.com",
        phone="9999999991",
        password_hash="hash",
        is_active=True
    )
    db_session.add(owner)

    epson_color = Printer(
        printer_id=uuid.uuid4(),
        owner_id=owner_id,
        printer_name="Epson L3150 Color",
        supports_bw=True,
        supports_color=True,
        status=PrinterStatus.ONLINE,
        is_available=True,
        current_queue=0
    )
    db_session.add(epson_color)
    db_session.commit()

    job = ActiveJob(
        job_id=uuid.uuid4(),
        owner_id=owner_id,
        customer_name="Bob Fallback",
        status=JobStatus.PENDING,
        payment_status=PaymentStatus.PAID
    )
    db_session.add(job)
    db_session.commit()

    file1 = JobFile(
        file_id=uuid.uuid4(),
        job_id=job.job_id,
        original_filename="BW_Document.pdf",
        print_type=PrintType.BW,
        paper_size=PaperSize.A4,
        duplex=False,
        page_count=2,
        copies=1
    )
    db_session.add(file1)
    db_session.commit()

    selected = assign_printer(job, db_session)
    assert selected is not None
    assert selected.printer_id == epson_color.printer_id


def test_color_job_rejects_monochrome_printer(db_session):
    """
    Strict hard capability gate: A color print job must NEVER be assigned to a monochrome printer.
    """
    owner_id = uuid.uuid4()
    owner = ShopOwner(
        owner_id=owner_id,
        owner_name="Test Owner",
        shop_name="Mono-Only Shop",
        email="mono@shop.com",
        phone="9999999992",
        password_hash="hash",
        is_active=True
    )
    db_session.add(owner)

    hp_mono = Printer(
        printer_id=uuid.uuid4(),
        owner_id=owner_id,
        printer_name="HP LaserJet Mono Only",
        supports_bw=True,
        supports_color=False,
        status=PrinterStatus.ONLINE,
        is_available=True
    )
    db_session.add(hp_mono)
    db_session.commit()

    job = ActiveJob(
        job_id=uuid.uuid4(),
        owner_id=owner_id,
        customer_name="Charlie Color Order",
        status=JobStatus.PENDING,
        payment_status=PaymentStatus.PAID
    )
    db_session.add(job)
    db_session.commit()

    file1 = JobFile(
        file_id=uuid.uuid4(),
        job_id=job.job_id,
        original_filename="Photos.pdf",
        print_type=PrintType.COLOR,
        paper_size=PaperSize.A4,
        duplex=False,
        page_count=3,
        copies=1
    )
    db_session.add(file1)
    db_session.commit()

    # Assignment should return None because no compatible color printer exists
    selected = assign_printer(job, db_session)
    assert selected is None
    assert job.assigned_printer_id is None


def test_color_job_selects_color_printer(db_session):
    """
    When customer selects COLOR and both mono & color printers exist,
    system must select the color printer.
    """
    owner_id = uuid.uuid4()
    owner = ShopOwner(
        owner_id=owner_id,
        owner_name="Test Owner",
        shop_name="Dual Shop",
        email="dual@shop.com",
        phone="9999999993",
        password_hash="hash",
        is_active=True
    )
    db_session.add(owner)

    hp_mono = Printer(
        printer_id=uuid.uuid4(),
        owner_id=owner_id,
        printer_name="HP Mono",
        supports_bw=True,
        supports_color=False,
        status=PrinterStatus.ONLINE,
        is_available=True
    )
    epson_color = Printer(
        printer_id=uuid.uuid4(),
        owner_id=owner_id,
        printer_name="Epson Color Pro",
        supports_bw=True,
        supports_color=True,
        status=PrinterStatus.ONLINE,
        is_available=True
    )
    db_session.add_all([hp_mono, epson_color])
    db_session.commit()

    job = ActiveJob(
        job_id=uuid.uuid4(),
        owner_id=owner_id,
        customer_name="David Color Job",
        status=JobStatus.PENDING,
        payment_status=PaymentStatus.PAID
    )
    db_session.add(job)
    db_session.commit()

    file1 = JobFile(
        file_id=uuid.uuid4(),
        job_id=job.job_id,
        original_filename="Poster.pdf",
        print_type=PrintType.COLOR,
        paper_size=PaperSize.A4,
        duplex=False,
        page_count=1,
        copies=2
    )
    db_session.add(file1)
    db_session.commit()

    selected = assign_printer(job, db_session)
    assert selected is not None
    assert selected.printer_id == epson_color.printer_id


def test_offline_printer_exclusion(db_session):
    """
    Printers marked OFFLINE or unavailable must be strictly excluded.
    """
    owner_id = uuid.uuid4()
    owner = ShopOwner(
        owner_id=owner_id,
        owner_name="Test Owner",
        shop_name="Offline Test Shop",
        email="off@shop.com",
        phone="9999999994",
        password_hash="hash",
        is_active=True
    )
    db_session.add(owner)

    hp_mono_offline = Printer(
        printer_id=uuid.uuid4(),
        owner_id=owner_id,
        printer_name="HP Offline",
        supports_bw=True,
        supports_color=False,
        status=PrinterStatus.OFFLINE,
        is_available=False
    )
    epson_online = Printer(
        printer_id=uuid.uuid4(),
        owner_id=owner_id,
        printer_name="Epson Online Fallback",
        supports_bw=True,
        supports_color=True,
        status=PrinterStatus.ONLINE,
        is_available=True
    )
    db_session.add_all([hp_mono_offline, epson_online])
    db_session.commit()

    job = ActiveJob(
        job_id=uuid.uuid4(),
        owner_id=owner_id,
        customer_name="Eve Offline Test",
        status=JobStatus.PENDING,
        payment_status=PaymentStatus.PAID
    )
    db_session.add(job)
    db_session.commit()

    file1 = JobFile(
        file_id=uuid.uuid4(),
        job_id=job.job_id,
        original_filename="Document.pdf",
        print_type=PrintType.BW,
        paper_size=PaperSize.A4,
        duplex=False,
        page_count=1,
        copies=1
    )
    db_session.add(file1)
    db_session.commit()

    selected = assign_printer(job, db_session)
    assert selected is not None
    assert selected.printer_id == epson_online.printer_id


def test_paper_size_a3_compatibility_gate(db_session):
    """
    A3 jobs must only be assigned to printers with supports_a3=True.
    """
    owner_id = uuid.uuid4()
    owner = ShopOwner(
        owner_id=owner_id,
        owner_name="Test Owner",
        shop_name="A3 Test Shop",
        email="a3@shop.com",
        phone="9999999995",
        password_hash="hash",
        is_active=True
    )
    db_session.add(owner)

    a4_printer = Printer(
        printer_id=uuid.uuid4(),
        owner_id=owner_id,
        printer_name="Standard A4 Printer",
        supports_bw=True,
        supports_color=True,
        supports_a3=False,
        status=PrinterStatus.ONLINE,
        is_available=True
    )
    a3_printer = Printer(
        printer_id=uuid.uuid4(),
        owner_id=owner_id,
        printer_name="Plotter / Large Format A3",
        supports_bw=True,
        supports_color=True,
        supports_a3=True,
        status=PrinterStatus.ONLINE,
        is_available=True
    )
    db_session.add_all([a4_printer, a3_printer])
    db_session.commit()

    job = ActiveJob(
        job_id=uuid.uuid4(),
        owner_id=owner_id,
        customer_name="Frank Blueprint",
        status=JobStatus.PENDING,
        payment_status=PaymentStatus.PAID
    )
    db_session.add(job)
    db_session.commit()

    file_a3 = JobFile(
        file_id=uuid.uuid4(),
        job_id=job.job_id,
        original_filename="Architectural_Blueprint.pdf",
        print_type=PrintType.BW,
        paper_size=PaperSize.A3,
        duplex=False,
        page_count=2,
        copies=1
    )
    db_session.add(file_a3)
    db_session.commit()

    selected = assign_printer(job, db_session)
    assert selected is not None
    assert selected.printer_id == a3_printer.printer_id
    assert selected.supports_a3 is True
