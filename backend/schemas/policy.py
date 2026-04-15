from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, model_validator

from models.policy import PolicyStatus
from models.quote import ProductType


class PolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    policy_number: str
    product: ProductType
    status: PolicyStatus
    inception_date: date
    expiry_date: date
    premium: Decimal
    current_data: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class PolicySummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    policy_number: str
    product: ProductType
    status: PolicyStatus
    inception_date: date
    expiry_date: date
    premium: Decimal
    created_at: datetime


class PolicyListResponse(BaseModel):
    items: list[PolicySummaryResponse]
    total: int
    page: int
    page_size: int


LOCKED_FIELDS = {"vehicle.registration", "vehicle.make", "vehicle.model", "vehicle.year"}
ENDORSABLE_FIELDS = {"customer_name", "customer_email", "customer_address"}


class EndorseRequest(BaseModel):
    changed_fields: dict[str, Any]
    reason: Optional[str] = None

    @model_validator(mode="after")
    def validate_fields(self):
        for field in self.changed_fields:
            if field in LOCKED_FIELDS:
                raise ValueError(f"'{field}' is locked and cannot be changed after bind")
            if field not in ENDORSABLE_FIELDS:
                raise ValueError(f"'{field}' is not endorsable. Allowed fields: {sorted(ENDORSABLE_FIELDS)}")
        if not self.changed_fields:
            raise ValueError("changed_fields must not be empty")
        return self
