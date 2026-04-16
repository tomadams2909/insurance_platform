from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from models.dealer_commission import CommissionType
from models.quote import ProductType


class CommissionCreateRequest(BaseModel):
    product: Optional[ProductType] = None
    commission_type: CommissionType
    commission_rate: Decimal = Field(gt=0)


class CommissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product: Optional[str]
    commission_type: CommissionType
    commission_rate: Decimal
    is_active: bool


class DealerCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    contact_email: Optional[EmailStr] = None
    address: Optional[dict[str, Any]] = None


class DealerUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1)
    contact_email: Optional[EmailStr] = None
    is_active: Optional[bool] = None


class DealerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    contact_email: Optional[str]
    address: Optional[dict[str, Any]]
    is_active: bool
    created_at: datetime
    commissions: list[CommissionResponse]
