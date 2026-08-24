from uuid import UUID
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.database.models import PricingBasis


# ==========================================
# Create Shop Settings
# ==========================================

class ShopSettingsCreate(BaseModel):

    default_printer_id: Optional[UUID] = None

    currency: str = "INR"

    tax_percentage: float = 0

    # Pricing Basis
    pricing_basis: PricingBasis = PricingBasis.PER_SIDE

    # Printing Options
    allow_bw_print: bool = True
    allow_color_print: bool = True
    allow_duplex: bool = True
    allow_mixed_print: bool = True
    allow_page_selection: bool = True

    # Upload Settings
    max_file_size_mb: int = 20
    max_files_per_job: int = 20


# ==========================================
# Update Shop Settings
# ==========================================

class ShopSettingsUpdate(BaseModel):

    default_printer_id: Optional[UUID] = None

    currency: Optional[str] = None

    tax_percentage: Optional[float] = None

    # Pricing Basis
    pricing_basis: Optional[PricingBasis] = None

    # Printing Options
    allow_bw_print: Optional[bool] = None
    allow_color_print: Optional[bool] = None
    allow_duplex: Optional[bool] = None
    allow_mixed_print: Optional[bool] = None
    allow_page_selection: Optional[bool] = None

    # Upload Settings
    max_file_size_mb: Optional[int] = None
    max_files_per_job: Optional[int] = None


# ==========================================
# Response
# ==========================================

class ShopSettingsResponse(BaseModel):

    setting_id: UUID
    owner_id: UUID

    default_printer_id: Optional[UUID]

    currency: str

    tax_percentage: float

    pricing_basis: PricingBasis

    # Printing Options
    allow_bw_print: bool
    allow_color_print: bool
    allow_duplex: bool
    allow_mixed_print: bool
    allow_page_selection: bool

    # Upload Settings
    max_file_size_mb: int
    max_files_per_job: int

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )