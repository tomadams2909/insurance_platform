import enum

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Numeric, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class ProductType(enum.Enum):
    GAP = "GAP"
    VRI = "VRI"
    COSMETIC = "COSMETIC"
    TYRE_ESSENTIAL = "TYRE_ESSENTIAL"
    TYRE_PLUS = "TYRE_PLUS"
    TLP = "TLP"


class QuoteStatus(enum.Enum):
    QUICK_QUOTE = "QUICK_QUOTE"
    QUOTED = "QUOTED"
    DECLINED = "DECLINED"


class Quote(Base):
    __tablename__ = "quotes"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    product = Column(Enum(ProductType), nullable=False)
    status = Column(Enum(QuoteStatus), nullable=False, default=QuoteStatus.QUICK_QUOTE)
    customer_name = Column(String, nullable=False)
    customer_dob = Column(String, nullable=True)
    customer_email = Column(String, nullable=True)
    customer_address = Column(JSON, nullable=True)
    term_months = Column(Integer, nullable=True)
    product_fields = Column(JSON, nullable=True)
    calculated_premium = Column(Numeric(10, 2), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    tenant = relationship("Tenant")
    created_by_user = relationship("User", foreign_keys=[created_by])
    vehicle = relationship("Vehicle", back_populates="quote", uselist=False)
