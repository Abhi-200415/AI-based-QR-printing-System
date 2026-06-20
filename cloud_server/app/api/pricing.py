from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import PricingRule
from app.schemas.pricing import PricingRuleCreate

router = APIRouter(
    prefix="/pricing",
    tags=["Pricing"]
)


@router.post("/rule")
def create_pricing_rule(
    rule: PricingRuleCreate,
    db: Session = Depends(get_db)
):
    new_rule = PricingRule(
        owner_id=rule.owner_id,
        rule_name=rule.rule_name,
        print_mode=rule.print_mode,
        min_pages=rule.min_pages,
        max_pages=rule.max_pages,
        price_per_page=rule.price_per_page
    )

    db.add(new_rule)
    db.commit()
    db.refresh(new_rule)

    return {
        "message": "Pricing rule created",
        "rule_id": str(new_rule.id)
    }


@router.get("/rules")
def get_pricing_rules(
    db: Session = Depends(get_db)
):
    return db.query(PricingRule).all()