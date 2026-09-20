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
    PrintType
)
from app.utils.logger import logger


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
    """
    page_count = file.page_count or 1
    paper_size = file.paper_size or PaperSize.A4
    print_type = file.print_type or PrintType.BW
    duplex = bool(file.duplex)

    # 1. Exact match with page range
    rule = (
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

    if rule:
        return rule

    # 2. Match without duplex constraint if no specific duplex rule
    rule = (
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

    if rule:
        return rule

    # 3. Match any active rule for this owner and print type
    rule = (
        db.query(PricingRule)
        .filter(
            PricingRule.owner_id == job.owner_id,
            PricingRule.print_type == print_type,
            PricingRule.is_active == True
        )
        .first()
    )

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

    if not files:
        job.subtotal = Decimal("0.00")
        job.tax = Decimal("0.00")
        job.total_amount = Decimal("0.00")
        db.commit()
        return Decimal("0.00")

    subtotal = Decimal("0.00")
    total_pages_count = 0
    total_files_count = len(files)
    total_copies_count = 0

    for file in files:
        subtotal += calculate_file_cost(job, file, db)
        total_pages_count += (file.page_count or 1) * (file.copies or 1)
        total_copies_count += (file.copies or 1)

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