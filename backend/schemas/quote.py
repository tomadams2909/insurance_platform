from decimal import Decimal
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict
from models.quote import ProductType


class VehicleQuickInput(BaseModel):
    purchase_price: Decimal
    registration: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    purchase_date: Optional[str] = None


class VehicleFullInput(BaseModel):
    purchase_price: Decimal
    registration: str
    make: str
    model: str
    year: int
    purchase_date: str
    finance_type: Optional[str] = None


class QuickQuoteRequest(BaseModel):
    customer_name: str
    product: ProductType
    term_months: int
    vehicle: VehicleQuickInput


class FullQuoteRequest(BaseModel):
    customer_name: str
    customer_dob: Optional[str] = None
    customer_email: Optional[str] = None
    customer_address: Optional[dict[str, Any]] = None
    product: ProductType
    term_months: int
    vehicle: VehicleFullInput
    product_fields: Optional[dict[str, Any]] = None


class QuickQuoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product: ProductType
    status: str
    term_months: int
    calculated_premium: Decimal
    customer_name: str


class VehicleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    registration: Optional[str]
    make: Optional[str]
    model: Optional[str]
    year: Optional[int]
    purchase_price: Optional[Decimal]
    purchase_date: Optional[str]
    finance_type: Optional[str]


class FullQuoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product: ProductType
    status: str
    term_months: int
    calculated_premium: Decimal
    customer_name: str
    customer_dob: Optional[str]
    customer_email: Optional[str]
    product_fields: Optional[dict[str, Any]]
    vehicle: VehicleResponse
