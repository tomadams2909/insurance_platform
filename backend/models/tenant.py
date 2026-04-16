from sqlalchemy import Boolean, Column, Integer, JSON, String, DateTime
from sqlalchemy.sql import func
from database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False, index=True)
    logo_url = Column(String, nullable=True)
    primary_colour = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    finance_company = Column(String, nullable=True)
    allowed_products = Column(JSON, nullable=True)
    favicon_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
