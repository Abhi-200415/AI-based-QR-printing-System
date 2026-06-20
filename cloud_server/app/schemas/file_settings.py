from pydantic import BaseModel
from typing import Optional


class FileSettingsUpdate(BaseModel):
    copies: int

    # bw | color | mixed
    print_mode: str

    # False = Single Side
    # True = Double Side
    duplex: bool

    # Only used when print_mode = mixed
    # Example:
    # 1-5,10,15-20
    color_page_ranges: Optional[str] = None