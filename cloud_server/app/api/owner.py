from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from app.database.connection import get_db
from app.database.models import ShopOwner
from app.schemas.owner import OwnerRegister, OwnerLogin

router = APIRouter(
    prefix="/owner",
    tags=["Owner"]
)

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)


@router.post("/register")
def register_owner(
    owner: OwnerRegister,
    db: Session = Depends(get_db)
):
    existing_owner = (
        db.query(ShopOwner)
        .filter(ShopOwner.email == owner.email)
        .first()
    )

    if existing_owner:
        raise HTTPException(
            status_code=400,
            detail="Email already exists"
        )

    hashed_password = pwd_context.hash(
        owner.password
    )

    new_owner = ShopOwner(
        shop_name=owner.shop_name,
        email=owner.email,
        password_hash=hashed_password,
        upi_id=owner.upi_id
    )

    db.add(new_owner)
    db.commit()
    db.refresh(new_owner)

    return {
        "message": "Owner registered successfully",
        "owner_id": str(new_owner.id)
    }


@router.post("/login")
def login_owner(
    owner: OwnerLogin,
    db: Session = Depends(get_db)
):
    existing_owner = (
        db.query(ShopOwner)
        .filter(ShopOwner.email == owner.email)
        .first()
    )

    if not existing_owner:
        raise HTTPException(
            status_code=404,
            detail="Owner not found"
        )

    if not pwd_context.verify(
        owner.password,
        existing_owner.password_hash
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid password"
        )

    return {
        "message": "Login successful",
        "owner_id": str(existing_owner.id),
        "shop_name": existing_owner.shop_name
    }
@router.get("/profile/{owner_id}")
def get_profile(
    owner_id: str,
    db: Session = Depends(get_db)
):
    owner = (
        db.query(ShopOwner)
        .filter(ShopOwner.id == owner_id)
        .first()
    )

    if not owner:
        raise HTTPException(
            status_code=404,
            detail="Owner not found"
        )

    return {
        "owner_id": str(owner.id),
        "shop_name": owner.shop_name,
        "email": owner.email,
        "upi_id": owner.upi_id
    }