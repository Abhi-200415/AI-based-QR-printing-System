from pydantic import BaseModel, EmailStr


class OwnerRegister(BaseModel):
    shop_name: str
    email: EmailStr
    password: str
    upi_id: str


class OwnerLogin(BaseModel):
    email: EmailStr
    password: str