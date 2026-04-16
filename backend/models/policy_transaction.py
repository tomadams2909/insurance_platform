import enum

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Numeric, JSON, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class TransactionType(enum.Enum):
    BIND = "BIND"
    ISSUE = "ISSUE"
    ENDORSEMENT = "ENDORSEMENT"
    CANCELLATION = "CANCELLATION"
    REINSTATEMENT = "REINSTATEMENT"


class PolicyTransaction(Base):
    __tablename__ = "policy_transactions"

    id = Column(Integer, primary_key=True, index=True)
    policy_id = Column(Integer, ForeignKey("policies.id"), nullable=False)
    transaction_type = Column(Enum(TransactionType), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    data_before = Column(JSON, nullable=True)
    data_after = Column(JSON, nullable=True)
    premium_delta = Column(Numeric(10, 2), nullable=True)
    reason_code = Column(String, nullable=True)
    reason_text = Column(Text, nullable=True)
    commission_data = Column(JSON, nullable=True)

    policy = relationship("Policy", back_populates="transactions")
    created_by_user = relationship("User", foreign_keys=[created_by])
