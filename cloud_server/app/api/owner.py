from uuid import uuid4, UUID
from typing import Optional
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status
)
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import ShopOwner, ShopSettings, PricingBasis
from app.core.security import hash_password, verify_password, create_access_token, get_current_owner
from app.services.analytics_service import get_dashboard_statistics

router = APIRouter(
    prefix="/owner",
    tags=["Owner"]
)


# ==========================================================
# Request / Response Schemas
# ==========================================================

class OwnerRegisterRequest(BaseModel):
    shop_name: str
    owner_name: str
    email: str
    phone: str
    password: str
    upi_id: Optional[str] = None
    address: Optional[str] = None
    shop_logo: Optional[str] = None


class OwnerLoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    owner_id: str
    shop_name: str
    owner_name: str


# ==========================================================
# Owner Registration
# ==========================================================

@router.post("/register")
def register_owner(
    data: OwnerRegisterRequest,
    db: Session = Depends(get_db)
):
    existing_owner = db.query(ShopOwner).filter(ShopOwner.email == data.email).first()
    if existing_owner:
        raise HTTPException(
            status_code=400,
            detail="An owner with this email already exists."
        )

    existing_phone = db.query(ShopOwner).filter(ShopOwner.phone == data.phone).first()
    if existing_phone:
        raise HTTPException(
            status_code=400,
            detail="An owner with this phone number already exists."
        )

    password_hash = hash_password(data.password)

    owner = ShopOwner(
        owner_id=uuid4(),
        shop_name=data.shop_name,
        owner_name=data.owner_name,
        shop_logo=data.shop_logo,
        email=data.email,
        phone=data.phone,
        password_hash=password_hash,
        upi_id=data.upi_id or f"{data.phone}@upi",
        address=data.address or "",
        is_active=True
    )

    # Automatically create default shop settings for the new owner
    settings = ShopSettings(
        owner_id=owner.owner_id,
        pricing_basis=PricingBasis.PER_SIDE,
        max_file_size_mb=50,
        tax_percentage=0.0
    )

    try:
        db.add(owner)
        db.add(settings)
        db.commit()
        db.refresh(owner)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Owner registration failed: {str(e)}"
        )

    return {
        "message": "Owner registered successfully",
        "owner_id": str(owner.owner_id),
        "shop_name": owner.shop_name,
        "owner_name": owner.owner_name,
        "email": owner.email,
        "phone": owner.phone,
        "upi_id": owner.upi_id,
        "address": owner.address,
        "is_active": owner.is_active
    }


# ==========================================================
# Owner Login (Generates JWT)
# ==========================================================

@router.post("/login", response_model=TokenResponse)
def login_owner(
    data: OwnerLoginRequest,
    db: Session = Depends(get_db)
):
    owner = db.query(ShopOwner).filter(ShopOwner.email == data.email).first()
    if not owner or not verify_password(data.password, owner.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    if not owner.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive."
        )

    token = create_access_token({"sub": str(owner.owner_id), "role": "owner"})

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        owner_id=str(owner.owner_id),
        shop_name=owner.shop_name,
        owner_name=owner.owner_name
    )


# ==========================================================
# Current Owner Profile
# ==========================================================

@router.get("/me")
def get_my_profile(
    current_owner: ShopOwner = Depends(get_current_owner)
):
    return {
        "owner_id": str(current_owner.owner_id),
        "shop_name": current_owner.shop_name,
        "owner_name": current_owner.owner_name,
        "email": current_owner.email,
        "phone": current_owner.phone,
        "upi_id": current_owner.upi_id,
        "address": current_owner.address,
        "qr_token": current_owner.qr_token,
        "qr_path": current_owner.qr_path,
        "is_active": current_owner.is_active
    }


# ==========================================================
# Get Owner By ID
# ==========================================================

@router.get("/{owner_id}")
def get_owner(
    owner_id: UUID,
    db: Session = Depends(get_db)
):
    owner = db.query(ShopOwner).filter(ShopOwner.owner_id == owner_id).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found.")

    return {
        "owner_id": str(owner.owner_id),
        "shop_name": owner.shop_name,
        "owner_name": owner.owner_name,
        "email": owner.email,
        "phone": owner.phone,
        "upi_id": owner.upi_id,
        "address": owner.address,
        "is_active": owner.is_active
    }


# ==========================================================
# Owner Dashboard Metrics
# ==========================================================

@router.get("/dashboard/{owner_id}")
def owner_dashboard(
    owner_id: UUID,
    db: Session = Depends(get_db)
):
    return get_dashboard_statistics(owner_id, db)