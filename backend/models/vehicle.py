from sqlalchemy import Column, Integer, String, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from database import Base


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    quote_id = Column(Integer, ForeignKey("quotes.id"), nullable=False, unique=True)
    registration = Column(String, nullable=True)
    make = Column(String, nullable=True)
    model = Column(String, nullable=True)
    year = Column(Integer, nullable=True)
    purchase_price = Column(Numeric(10, 2), nullable=True)
    purchase_date = Column(String, nullable=True)
    finance_type = Column(String, nullable=True)

    quote = relationship("Quote", back_populates="vehicle")
