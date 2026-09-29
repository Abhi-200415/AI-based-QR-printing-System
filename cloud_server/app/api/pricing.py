import uuid
from uuid import UUID
from decimal import Decimal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)

from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import (
    PricingRule,
    ActiveJob,
    PaperSize,
    PrintType
)

from app.schemas.pricing import (
    PricingRuleCreate,
    PricingRuleUpdate,
    QuickPricingUpdate
)

from app.services.pricing_engine import (
    calculate_job_cost,
    seed_default_pricing_rules
)

router = APIRouter(
    prefix="/pricing",
    tags=["Pricing"]
)


# ==========================================================
# Create Pricing Rule
# ==========================================================

@router.post("/rule")
def create_pricing_rule(
    rule: PricingRuleCreate,
    db: Session = Depends(get_db)
):
    pricing_rule = PricingRule(
        pricing_id=uuid.uuid4(),
        owner_id=rule.owner_id,
        paper_size=rule.paper_size,
        print_type=rule.print_type,
        duplex=rule.duplex,
        page_from=rule.page_from,
        page_to=rule.page_to or 9999,
        price_per_page=rule.price_per_page,
        is_active=True
    )

    db.add(pricing_rule)
    db.commit()
    db.refresh(pricing_rule)

    return {
        "success": True,
        "pricing_id": str(pricing_rule.pricing_id),
        "message": "Pricing rule created successfully."
    }


# ==========================================================
# Get Pricing Rules
# ==========================================================

@router.get("/owner/{owner_id}")
def get_pricing_rules(
    owner_id: UUID,
    db: Session = Depends(get_db)
):
    # Ensure baseline rules exist
    seed_default_pricing_rules(owner_id, db)

    rules = (
        db.query(PricingRule)
        .filter(
            PricingRule.owner_id == owner_id,
            PricingRule.is_active == True
        )
        .order_by(PricingRule.paper_size.asc(), PricingRule.print_type.asc(), PricingRule.page_from.asc())
        .all()
    )

    return [
        {
            "pricing_id": str(r.pricing_id),
            "owner_id": str(r.owner_id),
            "paper_size": r.paper_size.value if hasattr(r.paper_size, "value") else str(r.paper_size),
            "print_type": r.print_type.value if hasattr(r.print_type, "value") else str(r.print_type),
            "duplex": r.duplex,
            "page_from": r.page_from,
            "page_to": r.page_to,
            "price_per_page": float(r.price_per_page),
            "is_active": r.is_active
        }
        for r in rules
    ]


# ==========================================================
# Quick Pricing Update (Operator Rate Card)
# ==========================================================

@router.post("/quick-update/{owner_id}")
def quick_update_pricing(
    owner_id: UUID,
    rates: QuickPricingUpdate,
    db: Session = Depends(get_db)
):
    """
    Allows the operator to update standard A4 BW, A4 Color, A3 BW, A3 Color rates in a single click.
    """
    seed_default_pricing_rules(owner_id, db)

    targets = [
        (PaperSize.A4, PrintType.BW, rates.a4_bw),
        (PaperSize.A4, PrintType.COLOR, rates.a4_color),
        (PaperSize.A3, PrintType.BW, rates.a3_bw),
        (PaperSize.A3, PrintType.COLOR, rates.a3_color),
    ]

    for p_size, p_type, price in targets:
        rule = (
            db.query(PricingRule)
            .filter(
                PricingRule.owner_id == owner_id,
                PricingRule.paper_size == p_size,
                PricingRule.print_type == p_type,
                PricingRule.duplex == False,
                PricingRule.page_from == 1,
                PricingRule.is_active == True
            )
            .first()
        )
        if rule:
            rule.price_per_page = Decimal(str(price))
        else:
            new_rule = PricingRule(
                pricing_id=uuid.uuid4(),
                owner_id=owner_id,
                paper_size=p_size,
                print_type=p_type,
                duplex=False,
                page_from=1,
                page_to=9999,
                price_per_page=Decimal(str(price)),
                is_active=True
            )
            db.add(new_rule)

    db.commit()

    return {
        "success": True,
        "message": "Shop pricing rates updated successfully!"
    }


# ==========================================================
# Update Individual Pricing Rule
# ==========================================================

@router.put("/rule/{pricing_id}")
def update_pricing_rule(
    pricing_id: UUID,
    updates: PricingRuleUpdate,
    db: Session = Depends(get_db)
):
    rule = db.query(PricingRule).filter(PricingRule.pricing_id == pricing_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Pricing rule not found.")

    if updates.paper_size is not None:
        rule.paper_size = updates.paper_size
    if updates.print_type is not None:
        rule.print_type = updates.print_type
    if updates.duplex is not None:
        rule.duplex = updates.duplex
    if updates.page_from is not None:
        rule.page_from = updates.page_from
    if updates.page_to is not None:
        rule.page_to = updates.page_to
    if updates.price_per_page is not None:
        rule.price_per_page = Decimal(str(updates.price_per_page))
    if updates.is_active is not None:
        rule.is_active = updates.is_active

    db.commit()
    db.refresh(rule)

    return {
        "success": True,
        "pricing_id": str(rule.pricing_id),
        "message": "Pricing rule updated successfully."
    }


# ==========================================================
# Calculate Job Price
# ==========================================================

@router.get("/job/{job_id}")
def calculate_price(
    job_id: UUID,
    db: Session = Depends(get_db)
):
    job = (
        db.query(ActiveJob)
        .filter(
            ActiveJob.job_id == job_id
        )
        .first()
    )

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job not found."
        )

    calculate_job_cost(
        job_id,
        db
    )

    db.refresh(job)

    return {
        "job_id": str(job.job_id),
        "subtotal": float(job.subtotal),
        "tax": float(job.tax),
        "total_amount": float(job.total_amount)
    }


# ==========================================================
# Delete Pricing Rule
# ==========================================================

@router.delete("/rule/{pricing_id}")
def disable_pricing_rule(
    pricing_id: UUID,
    db: Session = Depends(get_db)
):
    rule = (
        db.query(PricingRule)
        .filter(
            PricingRule.pricing_id == pricing_id
        )
        .first()
    )

    if not rule:
        raise HTTPException(
            status_code=404,
            detail="Pricing rule not found."
        )

    rule.is_active = False
    db.commit()

    return {
        "success": True,
        "message": "Pricing rule disabled."
    }