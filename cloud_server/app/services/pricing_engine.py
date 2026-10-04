import uuid
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.database.models import (
    ActiveJob,
    JobFile,
    PricingRule,
    ShopSettings,
    PricingBasis,
    PaperSize,
    PrintType,
    FinishingService,
    JobFinishingService
)
from app.utils.logger import logger


# ==========================================================
# Default Finishing Services Seeder
# ==========================================================

def seed_default_finishing_services(owner_id, db: Session):
    """
    Seeds standard baseline finishing services for a shop owner if none exist.
    - Spiral Binding: Rs 30.00
    - Lamination: Rs 20.00
    - Stapling: Rs 5.00
    - Envelope: Rs 5.00
    - Transparent/Glass Sheet: Rs 3.00
    """
    try:
        existing = db.query(FinishingService).filter(FinishingService.owner_id == owner_id).first()
        if existing:
            return

        defaults = [
            ("Spiral Binding", "Protective spiral binding with front/back cover", Decimal("30.00"), "PER_ORDER"),
            ("Lamination", "Protective thermal pouch lamination", Decimal("20.00"), "PER_ORDER"),
            ("Stapling", "Corner or side staple fastening", Decimal("5.00"), "PER_ORDER"),
            ("Envelope", "Document security envelope", Decimal("5.00"), "PER_ORDER"),
            ("Transparent/Glass Sheet", "Clear transparent protective cover sheet", Decimal("3.00"), "PER_ORDER"),
        ]

        for name, desc, price, ctype in defaults:
            s = FinishingService(
                service_id=uuid.uuid4(),
                owner_id=owner_id,
                service_name=name,
                description=desc,
                price=price,
                charge_type=ctype,
                is_enabled=True
            )
            db.add(s)

        db.commit()
        logger.info(f"Seeded default finishing services for shop owner {owner_id}")
    except Exception as e:
        logger.warning(f"Could not seed default finishing services for owner {owner_id}: {e}")
        try:
            db.rollback()
        except Exception:
            pass


# ==========================================================
# Default Pricing Rules Seeder
# ==========================================================

def seed_default_pricing_rules(owner_id, db: Session):
    """
    Seeds standard baseline pricing rules for a newly registered or existing shop.
    A4 BW: Rs 2.00, A4 Color: Rs 10.00, A3 BW: Rs 5.00, A3 Color: Rs 20.00
    """
    try:
        existing = db.query(PricingRule).filter(PricingRule.owner_id == owner_id).first()
        if existing:
            return

        default_rules = [
            PricingRule(
                pricing_id=uuid.uuid4(),
                owner_id=owner_id,
                paper_size=PaperSize.A4,
                print_type=PrintType.BW,
                duplex=False,
                page_from=1,
                page_to=9999,
                price_per_page=Decimal("2.00"),
                is_active=True
            ),
            PricingRule(
                pricing_id=uuid.uuid4(),
                owner_id=owner_id,
                paper_size=PaperSize.A4,
                print_type=PrintType.COLOR,
                duplex=False,
                page_from=1,
                page_to=9999,
                price_per_page=Decimal("10.00"),
                is_active=True
            ),
            PricingRule(
                pricing_id=uuid.uuid4(),
                owner_id=owner_id,
                paper_size=PaperSize.A3,
                print_type=PrintType.BW,
                duplex=False,
                page_from=1,
                page_to=9999,
                price_per_page=Decimal("5.00"),
                is_active=True
            ),
            PricingRule(
                pricing_id=uuid.uuid4(),
                owner_id=owner_id,
                paper_size=PaperSize.A3,
                print_type=PrintType.COLOR,
                duplex=False,
                page_from=1,
                page_to=9999,
                price_per_page=Decimal("20.00"),
                is_active=True
            ),
        ]
        for r in default_rules:
            db.add(r)
        db.commit()
        logger.info(f"Seeded default pricing rules for shop owner {owner_id}")
    except Exception as e:
        logger.warning(f"Could not seed default pricing rules for owner {owner_id}: {e}")
        try:
            db.rollback()
        except Exception:
            pass


# ==========================================================
# Get Matching Pricing Rule
# ==========================================================

def get_pricing_rule(
    job: ActiveJob,
    file: JobFile,
    db: Session
) -> Optional[PricingRule]:
    """
    Finds the most specific active pricing rule for this file.
    Tries exact page range match first, then falls back to general rule.
    Auto-seeds default rules if none exist.
    """
    page_count = file.page_count or 1
    paper_size = file.paper_size or PaperSize.A4
    print_type = file.print_type or PrintType.BW
    duplex = bool(file.duplex)

    def _find():
        # 1. Exact match with page range
        r = (
            db.query(PricingRule)
            .filter(
                PricingRule.owner_id == job.owner_id,
                PricingRule.paper_size == paper_size,
                PricingRule.print_type == print_type,
                PricingRule.duplex == duplex,
                PricingRule.page_from <= page_count,
                PricingRule.page_to >= page_count,
                PricingRule.is_active == True
            )
            .first()
        )
        if r:
            return r

        # 2. Match without duplex constraint
        r = (
            db.query(PricingRule)
            .filter(
                PricingRule.owner_id == job.owner_id,
                PricingRule.paper_size == paper_size,
                PricingRule.print_type == print_type,
                PricingRule.is_active == True
            )
            .order_by(PricingRule.price_per_page.asc())
            .first()
        )
        if r:
            return r

        # 3. Match any active rule for this owner and print type
        r = (
            db.query(PricingRule)
            .filter(
                PricingRule.owner_id == job.owner_id,
                PricingRule.print_type == print_type,
                PricingRule.is_active == True
            )
            .first()
        )
        return r

    rule = _find()

    # If no rule found, auto-seed default rules and re-query
    if not rule and job.owner_id:
        seed_default_pricing_rules(job.owner_id, db)
        rule = _find()

    return rule


# ==========================================================
# Calculate Billable Units
# ==========================================================

def calculate_billable_units(
    file: JobFile,
    pricing_basis: PricingBasis
) -> int:
    page_count = file.page_count or 0
    if page_count <= 0:
        return 0

    if pricing_basis == PricingBasis.PER_SHEET:
        if file.duplex:
            return (page_count + 1) // 2
        return page_count

    return page_count  # PER_SIDE default


# ==========================================================
# Calculate Cost for One File
# ==========================================================

def calculate_file_cost(
    job: ActiveJob,
    file: JobFile,
    db: Session
) -> Decimal:
    rule = get_pricing_rule(job, file, db)

    if not rule:
        paper = file.paper_size.value if file.paper_size else "A4"
        ptype = file.print_type.value if file.print_type else "BW"
        raise HTTPException(
            status_code=400,
            detail=(
                f"No active pricing rule configured for paper size '{paper}' "
                f"and print type '{ptype}'. Please configure pricing rules in the shop settings."
            )
        )

    settings = (
        db.query(ShopSettings)
        .filter(ShopSettings.owner_id == job.owner_id)
        .first()
    )

    pricing_basis = PricingBasis.PER_SIDE
    if settings and settings.pricing_basis:
        pricing_basis = settings.pricing_basis

    billable_units_per_copy = calculate_billable_units(file, pricing_basis)
    copies = max(file.copies or 1, 1)
    total_billable_units = billable_units_per_copy * copies

    cost = Decimal(str(total_billable_units)) * Decimal(str(rule.price_per_page))
    file.estimated_cost = cost
    return cost


# ==========================================================
# Apply Finishing Services to Job
# ==========================================================

def apply_finishing_services_to_job(
    job: ActiveJob,
    service_selections: list,
    customer_reference: Optional[str],
    db: Session
):
    """
    Applies authoritative finishing service selections to an active job.
    Enforces shop isolation, active status, creates price snapshot records,
    and updates customer reference.
    """
    if customer_reference is not None:
        job.customer_reference = customer_reference.strip() if customer_reference else None

    # Clear existing selections for this job
    db.query(JobFinishingService).filter(JobFinishingService.job_id == job.job_id).delete()

    if not service_selections:
        job.finishing_status = "NONE"
        db.commit()
        return

    has_services = False
    for item in service_selections:
        srv_id = item.service_id if hasattr(item, "service_id") else item.get("service_id")
        qty = item.quantity if hasattr(item, "quantity") else item.get("quantity", 1)
        qty = max(1, int(qty or 1))
        fid = item.file_id if hasattr(item, "file_id") else item.get("file_id")

        if fid:
            # Verify file belongs to this job
            f_check = db.query(JobFile).filter(JobFile.file_id == fid, JobFile.job_id == job.job_id).first()
            if not f_check:
                raise HTTPException(
                    status_code=400,
                    detail=f"File {fid} does not belong to job {job.job_id}"
                )

        # Authoritative lookup: Must belong to THIS shop and be ENABLED
        service = (
            db.query(FinishingService)
            .filter(
                FinishingService.service_id == srv_id,
                FinishingService.owner_id == job.owner_id,
                FinishingService.is_enabled == True
            )
            .first()
        )
        if not service:
            raise HTTPException(
                status_code=400,
                detail=f"Finishing service {srv_id} is not available for this shop or is disabled."
            )

        unit_p = Decimal(str(service.price))
        total_p = unit_p * Decimal(str(qty))

        job_service = JobFinishingService(
            id=uuid.uuid4(),
            job_id=job.job_id,
            file_id=fid,
            service_id=service.service_id,
            service_name=service.service_name,
            unit_price=unit_p,
            quantity=qty,
            total_price=total_p
        )
        db.add(job_service)
        has_services = True

    job.finishing_status = "PENDING" if has_services else "NONE"
    db.commit()


# ==========================================================
# Calculate Total Job Cost
# ==========================================================

def calculate_job_cost(
    job_id,
    db: Session
) -> Decimal:
    job = (
        db.query(ActiveJob)
        .filter(ActiveJob.job_id == job_id)
        .first()
    )

    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    settings = (
        db.query(ShopSettings)
        .filter(ShopSettings.owner_id == job.owner_id)
        .first()
    )

    files = (
        db.query(JobFile)
        .filter(JobFile.job_id == job_id)
        .all()
    )

    # Printing cost
    printing_subtotal = Decimal("0.00")
    total_pages_count = 0
    total_files_count = len(files)
    total_copies_count = 0

    for file in files:
        printing_subtotal += calculate_file_cost(job, file, db)
        total_pages_count += (file.page_count or 1) * (file.copies or 1)
        total_copies_count += (file.copies or 1)

    # Finishing services cost
    finishing_services = (
        db.query(JobFinishingService)
        .filter(JobFinishingService.job_id == job_id)
        .all()
    )
    finishing_subtotal = Decimal("0.00")
    for fs in finishing_services:
        finishing_subtotal += Decimal(str(fs.total_price))

    subtotal = printing_subtotal + finishing_subtotal

    tax_percentage = Decimal("0.00")
    if settings and settings.tax_percentage is not None:
        tax_percentage = Decimal(str(settings.tax_percentage))

    tax = (subtotal * tax_percentage) / Decimal("100")
    total = subtotal + tax

    job.total_files = total_files_count
    job.total_pages = total_pages_count
    job.total_copies = total_copies_count
    job.subtotal = subtotal
    job.tax = tax
    job.total_amount = total

    db.commit()
    db.refresh(job)

    return total