from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)

from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import (
    PricingRule,
    ActiveJob
)

from app.schemas.pricing import PricingRuleCreate

from app.services.pricing_engine import calculate_job_cost

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

        owner_id=rule.owner_id,

        paper_size=rule.paper_size,

        print_type=rule.print_type,

        duplex=rule.duplex,

        page_from=rule.page_from,

        page_to=rule.page_to,

        price_per_page=rule.price_per_page
    )

    db.add(pricing_rule)

    db.commit()

    db.refresh(pricing_rule)

    return {

        "success": True,

        "pricing_id": str(
            pricing_rule.pricing_id
        )
    }


# ==========================================================
# Get Pricing Rules
# ==========================================================

@router.get("/owner/{owner_id}")
def get_pricing_rules(
    owner_id: UUID,
    db: Session = Depends(get_db)
):

    return (

        db.query(PricingRule)

        .filter(
            PricingRule.owner_id == owner_id,
            PricingRule.is_active == True
        )

        .all()

    )


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

    total = calculate_job_cost(
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