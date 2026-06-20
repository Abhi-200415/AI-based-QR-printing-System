from pydantic import BaseModel


class PrinterCreate(BaseModel):
    owner_id: str
    printer_name: str
    printer_mode: str
    pages_per_minute: int


class PrinterStatusUpdate(BaseModel):
    status: str
    current_queue: int