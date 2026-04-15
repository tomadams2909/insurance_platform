import enum

from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Enum, Numeric, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base
from models.quote import ProductType


class PolicyStatus(enum.Enum):
    BOUND = "BOUND"
    ISSUED = "ISSUED"
    CANCELLED = "CANCELLED"
    REINSTATED = "REINSTATED"


class Policy(Base):
    __tablename__ = "policies"

    id = Column(Integer, primary_key=True, index=True)
    quote_id = Column(Integer, ForeignKey("quotes.id"), nullable=False, unique=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    product = Column(Enum(ProductType), nullable=False)
    status = Column(Enum(PolicyStatus), nullable=False)
    policy_number = Column(String, unique=True, nullable=False, index=True)
    inception_date = Column(Date, nullable=False)
    expiry_date = Column(Date, nullable=False)
    premium = Column(Numeric(10, 2), nullable=False)
    current_data = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    quote = relationship("Quote")
    tenant = relationship("Tenant")
    transactions = relationship("PolicyTransaction", back_populates="policy")
    documents = relationship("PolicyDocument", back_populates="policy")
