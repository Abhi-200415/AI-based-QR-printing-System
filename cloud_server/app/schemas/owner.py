from uuid import UUID
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, ConfigDict


# ==========================================
# Owner Registration
# ==========================================

class OwnerRegister(BaseModel):
    shop_name: str
    owner_name: str
    email: EmailStr
    phone: str
    password: str
    upi_id: str
    address: str
    shop_logo: Optional[str] = None


# ==========================================
# Owner Login
# ==========================================

class OwnerLogin(BaseModel):
    email: EmailStr
    password: str


# ==========================================
# Owner Update
# ==========================================

class OwnerUpdate(BaseModel):
    shop_name: Optional[str] = None
    owner_name: Optional[str] = None
    phone: Optional[str] = None
    upi_id: Optional[str] = None
    address: Optional[str] = None
    shop_logo: Optional[str] = None


# ==========================================
# Owner Response
# ==========================================

class OwnerResponse(BaseModel):
    owner_id: UUID
    shop_name: str
    owner_name: str
    email: EmailStr
    phone: str
    upi_id: str
    address: str
    shop_logo: Optional[str]
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)