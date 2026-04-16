import enum

from sqlalchemy import Boolean, Column, Enum, ForeignKey, Integer, Numeric, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class CommissionType(enum.Enum):
    PERCENTAGE = "PERCENTAGE"
    FLAT_FEE = "FLAT_FEE"


class DealerCommission(Base):
    __tablename__ = "dealer_commissions"

    id = Column(Integer, primary_key=True, index=True)
    dealer_id = Column(Integer, ForeignKey("dealers.id"), nullable=False)

    # Commission resolution order:
    # (1) Active product-specific rate for this dealer  (product IS NOT NULL)
    # (2) Active dealer default rate                    (product IS NULL)
    # (3) Return zero — the caller decides if zero commission is valid
    product = Column(
        Enum(
            "GAP", "VRI", "COSMETIC", "TYRE_ESSENTIAL", "TYRE_PLUS", "TLP",
            name="producttype",
            create_type=False,
        ),
        nullable=True,
    )

    commission_type = Column(Enum(CommissionType), nullable=False)
    commission_rate = Column(Numeric(10, 4), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    dealer = relationship("Dealer", back_populates="commissions")
