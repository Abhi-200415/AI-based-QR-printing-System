from uuid import UUID
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.database.models import (
    PaperSize,
    PrintType
)


# ==========================================================
# Create Pricing Rule
# ==========================================================

class PricingRuleCreate(BaseModel):

    owner_id: UUID

    paper_size: PaperSize

    print_type: PrintType

    duplex: bool = False

    page_from: int = 1

    page_to: Optional[int] = None

    price_per_page: Decimal


# ==========================================================
# Update Pricing Rule
# ==========================================================

class PricingRuleUpdate(BaseModel):

    paper_size: Optional[PaperSize] = None

    print_type: Optional[PrintType] = None

    duplex: Optional[bool] = None

    page_from: Optional[int] = None

    page_to: Optional[int] = None

    price_per_page: Optional[Decimal] = None

    is_active: Optional[bool] = None


# ==========================================================
# Pricing Rule Response
# ==========================================================

class PricingRuleResponse(BaseModel):

    pricing_id: UUID

    owner_id: UUID

    paper_size: PaperSize

    print_type: PrintType

    duplex: bool

    page_from: int

    page_to: Optional[int]

    price_per_page: Decimal

    is_active: bool

    created_at: datetime

    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )