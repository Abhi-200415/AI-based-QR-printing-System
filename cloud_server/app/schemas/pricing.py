from pydantic import BaseModel

class PricingRuleCreate(BaseModel):
    rule_name: str
    print_mode: str
    min_pages: int
    max_pages: int
    price_per_page: float
    owner_id: str
    