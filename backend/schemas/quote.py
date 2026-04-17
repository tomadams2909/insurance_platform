from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from models.quote import ProductType, QuoteStatus, PaymentType

_FINANCE_TERMS = {12, 24, 36}


def _validate_year(v: Optional[int]) -> Optional[int]:
    if v is None:
        return v
    current_year = datetime.now().year
    if v < current_year - 10 or v > current_year + 1:
        raise ValueError(f"Vehicle year must be between {current_year - 10} and {current_year + 1}")
    return v


def _validate_date(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    try:
        datetime.strptime(v, "%Y-%m-%d")
    except ValueError:
        raise ValueError("Date must be in YYYY-MM-DD format")
    return v


def _validate_dob(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    try:
        dob = datetime.strptime(v, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("customer_dob must be in YYYY-MM-DD format")
    today = date.today()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    if age < 18:
        raise ValueError("Customer must be at least 18 years old")
    return v


class VehicleQuickInput(BaseModel):
    purchase_price: Decimal = Field(gt=0, le=200000)
    registration: Optional[str] = Field(default=None, min_length=1, max_length=10)
    make: Optional[str] = Field(default=None, min_length=1)
    model: Optional[str] = Field(default=None, min_length=1)
    year: Optional[int] = None
    purchase_date: Optional[str] = None

    @field_validator("year")
    @classmethod
    def validate_year(cls, v):
        return _validate_year(v)

    @field_validator("purchase_date")
    @classmethod
    def validate_purchase_date(cls, v):
        return _validate_date(v)


class VehicleFullInput(BaseModel):
    purchase_price: Decimal = Field(gt=0, le=200000)
    registration: str = Field(min_length=1, max_length=10)
    make: str = Field(min_length=1)
    model: str = Field(min_length=1)
    year: int
    purchase_date: str
    finance_type: Optional[Literal["PCP", "HP", "cash", "loan"]] = None

    @field_validator("year")
    @classmethod
    def validate_year(cls, v):
        return _validate_year(v)

    @field_validator("purchase_date")
    @classmethod
    def validate_purchase_date(cls, v):
        return _validate_date(v)


class QuickQuoteRequest(BaseModel):
    customer_name: str = Field(min_length=1, max_length=100)
    product: ProductType
    term_months: Literal[12, 24, 36, 48, 60]
    vehicle: VehicleQuickInput
    payment_type: PaymentType = PaymentType.CASH
    finance_deposit: Optional[Decimal] = Field(default=None, ge=0)
    finance_term_months: Optional[int] = None

    @model_validator(mode="after")
    def validate_finance_fields(self):
        if self.payment_type == PaymentType.FINANCE:
            if self.finance_deposit is None:
                raise ValueError("finance_deposit is required when payment_type is FINANCE")
            if self.finance_term_months is None:
                raise ValueError("finance_term_months is required when payment_type is FINANCE")
            if self.finance_term_months not in _FINANCE_TERMS:
                raise ValueError("finance_term_months must be 12, 24, or 36")
        return self


class FullQuoteRequest(BaseModel):
    customer_name: str = Field(min_length=1, max_length=100)
    customer_dob: Optional[str] = None
    customer_email: Optional[EmailStr] = None
    customer_address: Optional[dict[str, Any]] = None
    product: ProductType
    term_months: Literal[12, 24, 36, 48, 60]
    vehicle: VehicleFullInput
    product_fields: Optional[dict[str, Any]] = None
    payment_type: PaymentType = PaymentType.CASH
    finance_deposit: Optional[Decimal] = Field(default=None, ge=0)
    finance_term_months: Optional[int] = None

    @field_validator("customer_dob")
    @classmethod
    def validate_dob(cls, v):
        return _validate_dob(v)

    @model_validator(mode="after")
    def validate_finance_fields(self):
        if self.payment_type == PaymentType.FINANCE:
            if self.finance_deposit is None:
                raise ValueError("finance_deposit is required when payment_type is FINANCE")
            if self.finance_term_months is None:
                raise ValueError("finance_term_months is required when payment_type is FINANCE")
            if self.finance_term_months not in _FINANCE_TERMS:
                raise ValueError("finance_term_months must be 12, 24, or 36")
        return self


class PromoteQuoteRequest(BaseModel):
    customer_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    customer_dob: Optional[str] = None
    customer_email: Optional[EmailStr] = None
    customer_address: Optional[dict[str, Any]] = None
    term_months: Optional[Literal[12, 24, 36, 48, 60]] = None
    vehicle: VehicleFullInput
    product_fields: Optional[dict[str, Any]] = None

    @field_validator("customer_dob")
    @classmethod
    def validate_dob(cls, v):
        return _validate_dob(v)


class QuickQuoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product: ProductType
    status: QuoteStatus
    term_months: int
    calculated_premium: Decimal
    customer_name: str
    payment_type: PaymentType
    finance_breakdown: Optional[dict[str, Any]]


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
    status: QuoteStatus
    term_months: int
    calculated_premium: Decimal
    customer_name: str
    customer_dob: Optional[str]
    customer_email: Optional[str]
    product_fields: Optional[dict[str, Any]]
    vehicle: VehicleResponse
    payment_type: PaymentType
    finance_breakdown: Optional[dict[str, Any]]


class QuoteDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product: ProductType
    status: QuoteStatus
    term_months: int
    calculated_premium: Decimal
    customer_name: str
    customer_dob: Optional[str]
    customer_email: Optional[str]
    customer_address: Optional[dict[str, Any]]
    product_fields: Optional[dict[str, Any]]
    vehicle_category: Optional[int]
    created_at: datetime
    vehicle: VehicleResponse
    payment_type: PaymentType
    finance_breakdown: Optional[dict[str, Any]]


class QuoteSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product: ProductType
    status: QuoteStatus
    term_months: int
    calculated_premium: Decimal
    customer_name: str
    customer_email: Optional[str]
    payment_type: PaymentType


class QuoteListResponse(BaseModel):
    items: list[QuoteSummaryResponse]
    total: int
    page: int
    page_size: int
