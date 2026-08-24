from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from pydantic import BaseModel

from sqlalchemy.orm import Session

from passlib.context import CryptContext

from app.database.connection import get_db
from app.database.models import ShopOwner


# ==========================================================
# Router
# ==========================================================

router = APIRouter(
    prefix="/owner",
    tags=["Owner"]
)


# ==========================================================
# Password Hashing
# ==========================================================

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)


# ==========================================================
# Request Schema
# ==========================================================

class OwnerRegisterRequest(BaseModel):

    shop_name: str
    owner_name: str
    email: str
    phone: str
    password: str
    upi_id: str
    address: str
    shop_logo: str | None = None


# ==========================================================
# Owner Registration
# ==========================================================

@router.post("/register")
def register_owner(
    data: OwnerRegisterRequest,
    db: Session = Depends(get_db)
):

    # ------------------------------------------------------
    # Check Existing Email
    # ------------------------------------------------------

    existing_owner = (
        db.query(ShopOwner)
        .filter(
            ShopOwner.email == data.email
        )
        .first()
    )

    if existing_owner:

        raise HTTPException(
            status_code=400,
            detail="An owner with this email already exists."
        )

    # ------------------------------------------------------
    # Check Existing Phone
    # ------------------------------------------------------

    existing_phone = (
        db.query(ShopOwner)
        .filter(
            ShopOwner.phone == data.phone
        )
        .first()
    )

    if existing_phone:

        raise HTTPException(
            status_code=400,
            detail="An owner with this phone number already exists."
        )

    # ------------------------------------------------------
    # Hash Password
    # ------------------------------------------------------

    password_hash = pwd_context.hash(
        data.password
    )

    # ------------------------------------------------------
    # Create Owner
    # ------------------------------------------------------

    owner = ShopOwner(

        owner_id=uuid4(),

        shop_name=data.shop_name,

        owner_name=data.owner_name,

        shop_logo=data.shop_logo,

        email=data.email,

        phone=data.phone,

        password_hash=password_hash,

        upi_id=data.upi_id,

        address=data.address,

        is_active=True
    )

    # ------------------------------------------------------
    # Save To Database
    # ------------------------------------------------------

    try:

        db.add(owner)

        db.commit()

        db.refresh(owner)

    except Exception as e:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Owner registration failed: {str(e)}"
        )

    # ------------------------------------------------------
    # Response
    # ------------------------------------------------------

    return {

        "message": "Owner registered successfully",

        "owner_id": str(
            owner.owner_id
        ),

        "shop_name": owner.shop_name,

        "owner_name": owner.owner_name,

        "email": owner.email,

        "phone": owner.phone,

        "upi_id": owner.upi_id,

        "address": owner.address,

        "shop_logo": owner.shop_logo,

        "is_active": owner.is_active
    }


# ==========================================================
# Get Owner
# ==========================================================

@router.get("/{owner_id}")
def get_owner(
    owner_id: str,
    db: Session = Depends(get_db)
):

    owner = (
        db.query(ShopOwner)
        .filter(
            ShopOwner.owner_id == owner_id
        )
        .first()
    )

    if not owner:

        raise HTTPException(
            status_code=404,
            detail="Owner not found."
        )

    return {

        "owner_id": str(
            owner.owner_id
        ),

        "shop_name": owner.shop_name,

        "owner_name": owner.owner_name,

        "email": owner.email,

        "phone": owner.phone,

        "upi_id": owner.upi_id,

        "address": owner.address,

        "shop_logo": owner.shop_logo,

        "is_active": owner.is_active
    }