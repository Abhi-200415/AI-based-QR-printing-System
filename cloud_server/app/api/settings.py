from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)

from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import ShopSettings

from app.schemas.settings import (
    ShopSettingsCreate,
    ShopSettingsUpdate,
    ShopSettingsResponse
)


# ==========================================================
# Router
# ==========================================================

router = APIRouter(
    prefix="/settings",
    tags=["Settings"]
)


# ==========================================================
# Create / Get Shop Settings
# ==========================================================

@router.post(
    "/owner/{owner_id}",
    response_model=ShopSettingsResponse
)
def create_shop_settings(
    owner_id: UUID,
    data: ShopSettingsCreate,
    db: Session = Depends(get_db)
):

    existing = (
        db.query(ShopSettings)
        .filter(
            ShopSettings.owner_id == owner_id
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Shop settings already exist."
        )

    settings = ShopSettings(
        owner_id=owner_id,
        default_printer_id=data.default_printer_id,
        currency=data.currency,
        tax_percentage=data.tax_percentage,
        pricing_basis=data.pricing_basis,
        allow_bw_print=data.allow_bw_print,
        allow_color_print=data.allow_color_print,
        allow_duplex=data.allow_duplex,
        allow_mixed_print=data.allow_mixed_print,
        allow_page_selection=data.allow_page_selection,
        max_file_size_mb=data.max_file_size_mb,
        max_files_per_job=data.max_files_per_job
    )

    db.add(settings)
    db.commit()
    db.refresh(settings)

    return settings


# ==========================================================
# Get Shop Settings
# ==========================================================

@router.get(
    "/owner/{owner_id}",
    response_model=ShopSettingsResponse
)
def get_shop_settings(
    owner_id: UUID,
    db: Session = Depends(get_db)
):

    settings = (
        db.query(ShopSettings)
        .filter(
            ShopSettings.owner_id == owner_id
        )
        .first()
    )

    if not settings:
        raise HTTPException(
            status_code=404,
            detail="Shop settings not found."
        )

    return settings


# ==========================================================
# Update Shop Settings
# ==========================================================

@router.put(
    "/owner/{owner_id}",
    response_model=ShopSettingsResponse
)
def update_shop_settings(
    owner_id: UUID,
    data: ShopSettingsUpdate,
    db: Session = Depends(get_db)
):

    settings = (
        db.query(ShopSettings)
        .filter(
            ShopSettings.owner_id == owner_id
        )
        .first()
    )

    if not settings:
        raise HTTPException(
            status_code=404,
            detail="Shop settings not found."
        )

    update_data = data.model_dump(
        exclude_unset=True
    )

    for field, value in update_data.items():

        setattr(
            settings,
            field,
            value
        )

    db.commit()
    db.refresh(settings)

    return settings