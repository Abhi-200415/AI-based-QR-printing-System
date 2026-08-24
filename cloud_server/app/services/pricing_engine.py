from decimal import Decimal

from sqlalchemy.orm import Session

from app.database.models import (
    ActiveJob,
    JobFile,
    PricingRule,
    ShopSettings,
    PricingBasis
)


# ==========================================================
# Get Matching Pricing Rule
# ==========================================================

def get_pricing_rule(
    job: ActiveJob,
    file: JobFile,
    db: Session
):

    return (
        db.query(PricingRule)
        .filter(
            PricingRule.owner_id == job.owner_id,
            PricingRule.paper_size == file.paper_size,
            PricingRule.print_type == file.print_type,
            PricingRule.duplex == file.duplex,
            PricingRule.page_from <= file.page_count,
            PricingRule.page_to >= file.page_count,
            PricingRule.is_active == True
        )
        .first()
    )


# ==========================================================
# Calculate Billable Units
# ==========================================================

def calculate_billable_units(
    file: JobFile,
    pricing_basis: PricingBasis
) -> int:
    """
    Calculate the number of billable printing units.

    PER_SIDE:
        Every PDF page is billed.

        Example:
            42-page PDF
            = 42 billable sides

    PER_SHEET:
        Single-sided:
            42 pages = 42 physical sheets

        Duplex:
            42 pages = 21 physical sheets

        Odd page count:
            41 pages = 21 physical sheets
    """

    page_count = file.page_count or 0

    if page_count <= 0:
        return 0

    # ------------------------------------------------------
    # Per printed side/page
    # ------------------------------------------------------

    if pricing_basis == PricingBasis.PER_SIDE:

        return page_count

    # ------------------------------------------------------
    # Per physical sheet
    # ------------------------------------------------------

    if pricing_basis == PricingBasis.PER_SHEET:

        if file.duplex:

            return (page_count + 1) // 2

        return page_count

    # ------------------------------------------------------
    # Safe fallback
    # ------------------------------------------------------

    return page_count


# ==========================================================
# Calculate Cost for One File
# ==========================================================

def calculate_file_cost(
    job: ActiveJob,
    file: JobFile,
    db: Session
) -> Decimal:

    rule = get_pricing_rule(
        job,
        file,
        db
    )

    if not rule:

        file.estimated_cost = Decimal("0.00")

        return Decimal("0.00")

    # ------------------------------------------------------
    # Get owner's pricing settings
    # ------------------------------------------------------

    settings = (
        db.query(ShopSettings)
        .filter(
            ShopSettings.owner_id == job.owner_id
        )
        .first()
    )

    # ------------------------------------------------------
    # Default pricing basis
    # ------------------------------------------------------

    pricing_basis = PricingBasis.PER_SIDE

    if settings and settings.pricing_basis:

        pricing_basis = settings.pricing_basis

    # ------------------------------------------------------
    # Calculate billable units for ONE copy
    # ------------------------------------------------------

    billable_units_per_copy = calculate_billable_units(
        file,
        pricing_basis
    )

    # ------------------------------------------------------
    # Apply copies
    # ------------------------------------------------------

    copies = file.copies or 1

    total_billable_units = (
        billable_units_per_copy * copies
    )

    # ------------------------------------------------------
    # Calculate cost
    # ------------------------------------------------------

    cost = (
        Decimal(total_billable_units)
        * rule.price_per_page
    )

    file.estimated_cost = cost

    return cost


# ==========================================================
# Calculate Total Job Cost
# ==========================================================

def calculate_job_cost(
    job_id,
    db: Session
):

    job = (
        db.query(ActiveJob)
        .filter(
            ActiveJob.job_id == job_id
        )
        .first()
    )

    if not job:

        return Decimal("0.00")

    # ------------------------------------------------------
    # Get owner settings
    # ------------------------------------------------------

    settings = (
        db.query(ShopSettings)
        .filter(
            ShopSettings.owner_id == job.owner_id
        )
        .first()
    )

    # ------------------------------------------------------
    # Get job files
    # ------------------------------------------------------

    files = (
        db.query(JobFile)
        .filter(
            JobFile.job_id == job_id
        )
        .all()
    )

    # ------------------------------------------------------
    # Calculate subtotal
    # ------------------------------------------------------

    subtotal = Decimal("0.00")

    for file in files:

        subtotal += calculate_file_cost(
            job,
            file,
            db
        )

    # ------------------------------------------------------
    # Tax
    # ------------------------------------------------------

    tax_percentage = Decimal("0.00")

    if settings and settings.tax_percentage is not None:

        tax_percentage = Decimal(
            str(settings.tax_percentage)
        )

    tax = (
        subtotal
        * tax_percentage
        / Decimal("100")
    )

    # ------------------------------------------------------
    # Total
    # ------------------------------------------------------

    total = subtotal + tax

    # ------------------------------------------------------
    # Update job
    # ------------------------------------------------------

    job.subtotal = subtotal

    job.tax = tax

    job.total_amount = total

    db.commit()

    db.refresh(job)

    return total