from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from models.document import DocumentType
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
    dealer_fee: Optional[Decimal]
    broker_commission: Optional[Decimal]
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


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    transaction_type: str
    created_at: datetime
    created_by: int
    premium_delta: Optional[Decimal]
    reason_text: Optional[str]
    description: str


class DocumentSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_type: DocumentType
    filename: str
    created_at: datetime


class CancelRequest(BaseModel):
    reason: str = Field(min_length=1)
    cancellation_date: Optional[date] = None


class ReinstateRequest(BaseModel):
    reinstatement_date: Optional[date] = None


LOCKED_FIELDS = {"vehicle.registration", "vehicle.make", "vehicle.model", "vehicle.year"}
ENDORSABLE_FIELDS = {"customer_name", "customer_email", "customer_address"}


class EndorseRequest(BaseModel):
    changed_fields: dict[str, Any] = Field(default_factory=dict)
    reason: Optional[str] = None
    premium_delta: Decimal = Decimal("0.00")

    @model_validator(mode="after")
    def validate_fields(self):
        for field in self.changed_fields:
            if field in LOCKED_FIELDS:
                raise ValueError(f"'{field}' is locked and cannot be changed after bind")
            if field not in ENDORSABLE_FIELDS:
                raise ValueError(f"'{field}' is not endorsable. Allowed fields: {sorted(ENDORSABLE_FIELDS)}")
        if not self.changed_fields and self.premium_delta == 0:
            raise ValueError("Endorsement must change at least one field or have a non-zero premium_delta")
        return self
