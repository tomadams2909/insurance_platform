from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

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
