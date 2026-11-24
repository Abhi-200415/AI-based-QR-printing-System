import os
import sys
import uuid
import pytest
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.database.connection import Base, get_db
from app.database.models import (
    ShopOwner,
    Printer,
    PrinterStatus,
    ActiveJob,
    JobFile,
    FinishingService,
    JobFinishingService,
    PrintType,
    PaperSize,
    Orientation,
    JobStatus,
    PaymentStatus
)
from app.services.pricing_engine import (
    apply_finishing_services_to_job,
    calculate_job_cost,
    seed_default_finishing_services
)


@pytest.fixture
def client_and_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = Session()

    def override_get_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    yield client, db

    db.close()
    app.dependency_overrides.clear()


def test_multifile_finishing_services_independent_preservation(client_and_db):
    """
    PART 2 A TEST: In a multi-file order:
    File 1: Assignment.pdf with Lamination
    File 2: Project_Report.pdf with Spiral Binding
    Saving File 2 must NOT erase File 1's lamination! Both must be preserved.
    """
    client, db = client_and_db

    owner_id = uuid.uuid4()
    owner = ShopOwner(
        owner_id=owner_id,
        owner_name="Test Owner",
        shop_name="Finishing Test Shop",
        email="finish@shop.com",
        phone="9999999990",
        password_hash="hash",
        is_active=True
    )
    db.add(owner)
    db.commit()

    # Seed finishing services (Lamination: 20.00, Spiral Binding: 40.00)
    seed_default_finishing_services(owner_id, db)
    services = db.query(FinishingService).filter(FinishingService.owner_id == owner_id).all()
    lam_service = next(s for s in services if "laminat" in s.service_name.lower())
    spiral_service = next(s for s in services if "spiral" in s.service_name.lower() or "binding" in s.service_name.lower())

    job = ActiveJob(
        job_id=uuid.uuid4(),
        owner_id=owner_id,
        customer_name="Alice Multi-File",
        customer_reference="Order-Ref-101",
        status=JobStatus.PENDING,
        payment_status=PaymentStatus.PENDING
    )
    db.add(job)
    db.commit()

    file1 = JobFile(
        file_id=uuid.uuid4(),
        job_id=job.job_id,
        original_filename="Assignment.pdf",
        print_type=PrintType.BW,
        paper_size=PaperSize.A4,
        duplex=False,
        page_count=2,
        copies=2
    )
    file2 = JobFile(
        file_id=uuid.uuid4(),
        job_id=job.job_id,
        original_filename="Project_Report.pdf",
        print_type=PrintType.COLOR,
        paper_size=PaperSize.A4,
        duplex=True,
        page_count=10,
        copies=1
    )
    db.add_all([file1, file2])
    db.commit()

    # 1. Apply Lamination to File 1
    apply_finishing_services_to_job(
        job=job,
        service_selections=[{"service_id": str(lam_service.service_id), "file_id": file1.file_id, "quantity": 1}],
        customer_reference="Order-Ref-101",
        db=db,
        target_file_id=file1.file_id
    )

    # Verify File 1 has lamination
    f1_services = db.query(JobFinishingService).filter(JobFinishingService.file_id == file1.file_id).all()
    assert len(f1_services) == 1
    assert f1_services[0].service_id == lam_service.service_id

    # 2. Apply Spiral Binding to File 2
    apply_finishing_services_to_job(
        job=job,
        service_selections=[{"service_id": str(spiral_service.service_id), "file_id": file2.file_id, "quantity": 1}],
        customer_reference="Order-Ref-101",
        db=db,
        target_file_id=file2.file_id
    )

    # 3. VERIFY: File 1's Lamination is STILL PRESENT! File 2's Spiral Binding is ALSO present!
    all_job_services = db.query(JobFinishingService).filter(JobFinishingService.job_id == job.job_id).all()
    assert len(all_job_services) == 2

    f1_services_after = db.query(JobFinishingService).filter(JobFinishingService.file_id == file1.file_id).all()
    f2_services_after = db.query(JobFinishingService).filter(JobFinishingService.file_id == file2.file_id).all()

    assert len(f1_services_after) == 1
    assert f1_services_after[0].service_id == lam_service.service_id

    assert len(f2_services_after) == 1
    assert f2_services_after[0].service_id == spiral_service.service_id

    # 4. Calculate total cost: includes both finishing charges
    calculate_job_cost(job.job_id, db)
    db.refresh(job)
    assert job.finishing_status == "PENDING"
    assert job.total_amount > Decimal("60.00")  # At least 20 (lam) + 40 (spiral) + print cost


def test_live_queue_api_contains_rich_file_finishing_and_customer_data(client_and_db):
    """
    PART 2 C & D TEST: Verify GET /queue/ returns customer name, file specs, and finishing badges.
    """
    client, db = client_and_db

    owner_id = uuid.uuid4()
    owner = ShopOwner(
        owner_id=owner_id,
        owner_name="Test Owner",
        shop_name="Queue Display Shop",
        email="queue@shop.com",
        phone="9999999991",
        password_hash="hash",
        is_active=True
    )
    db.add(owner)
    db.commit()

    printer = Printer(
        printer_id=uuid.uuid4(),
        owner_id=owner_id,
        printer_name="HP LaserJet MFP Pro",
        supports_bw=True,
        supports_color=False,
        status=PrinterStatus.ONLINE,
        is_available=True
    )
    db.add(printer)
    db.commit()

    seed_default_finishing_services(owner_id, db)
    services = db.query(FinishingService).filter(FinishingService.owner_id == owner_id).all()
    lam_service = next(s for s in services if "laminat" in s.service_name.lower())

    job = ActiveJob(
        job_id=uuid.uuid4(),
        owner_id=owner_id,
        customer_name="Nanda Kumar",
        customer_reference="Ref-NK-99",
        assigned_printer_id=printer.printer_id,
        queue_position=1,
        status=JobStatus.QUEUED,
        payment_status=PaymentStatus.PAID
    )
    db.add(job)
    db.commit()

    file1 = JobFile(
        file_id=uuid.uuid4(),
        job_id=job.job_id,
        original_filename="Annual_Report_2026.pdf",
        print_type=PrintType.BW,
        paper_size=PaperSize.A4,
        duplex=False,
        page_count=15,
        copies=2,
        assigned_printer_id=printer.printer_id
    )
    db.add(file1)
    db.commit()

    apply_finishing_services_to_job(
        job=job,
        service_selections=[{"service_id": str(lam_service.service_id), "file_id": file1.file_id, "quantity": 1}],
        customer_reference="Ref-NK-99",
        db=db,
        target_file_id=file1.file_id
    )

    # Call GET /queue/
    response = client.get("/queue/")
    assert response.status_code == 200
    queue_data = response.json()

    assert len(queue_data) >= 1
    target = next((q for q in queue_data if q["job_id"] == str(job.job_id)), None)
    assert target is not None

    # Check Customer Name and Reference
    assert target["customer_name"] == "Nanda Kumar"
    assert target["customer_reference"] == "Ref-NK-99"

    # Check Assigned Printer Name
    assert target["assigned_printer_name"] == "HP LaserJet MFP Pro"

    # Check Rich File Info and Finishing Services
    assert len(target["files"]) == 1
    file_info = target["files"][0]
    assert file_info["filename"] == "Annual_Report_2026.pdf"
    assert file_info["lamination"] is True
    assert "Lamination" in file_info["finishing_services"][0]
    assert file_info["assigned_printer_name"] == "HP LaserJet MFP Pro"
