import enum

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, LargeBinary
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class DocumentType(enum.Enum):
    POLICY_SCHEDULE = "POLICY_SCHEDULE"
    ENDORSEMENT_CERTIFICATE = "ENDORSEMENT_CERTIFICATE"
    CANCELLATION_NOTICE = "CANCELLATION_NOTICE"
    REINSTATEMENT_NOTICE = "REINSTATEMENT_NOTICE"


class PolicyDocument(Base):
    __tablename__ = "policy_documents"

    id = Column(Integer, primary_key=True, index=True)
    policy_id = Column(Integer, ForeignKey("policies.id"), nullable=False)
    document_type = Column(Enum(DocumentType), nullable=False)
    filename = Column(String, nullable=False)
    content = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    policy = relationship("Policy", back_populates="documents")
