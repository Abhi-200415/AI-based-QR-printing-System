from pydantic import BaseModel
from uuid import UUID


class JobCreate(BaseModel):
    session_id: UUID
    username: str
    payment_method: str