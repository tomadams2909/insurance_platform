from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict
from models.quote import ProductType


class VehicleQuickInput(BaseModel):
    purchase_price: Decimal
    registration: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    purchase_date: Optional[str] = None


class QuickQuoteRequest(BaseModel):
    customer_name: str
    product: ProductType
    term_months: int
    vehicle: VehicleQuickInput


class QuickQuoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product: ProductType
    status: str
    term_months: int
    calculated_premium: Decimal
    customer_name: str
