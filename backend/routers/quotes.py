from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models.quote import Quote, QuoteStatus
from models.vehicle import Vehicle
from models.user import User, UserRole
from schemas.quote import QuickQuoteRequest, QuickQuoteResponse
from services.pricing import calculate_premium
from auth.dependencies import require_role

router = APIRouter(prefix="/quotes", tags=["quotes"])

_QUOTE_ROLES = (UserRole.BROKER, UserRole.UNDERWRITER, UserRole.TENANT_ADMIN, UserRole.SUPER_ADMIN)


@router.post("/quick", response_model=QuickQuoteResponse, status_code=201)
def create_quick_quote(
    payload: QuickQuoteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_QUOTE_ROLES)),
):
    premium = calculate_premium(
        product=payload.product.value,
        vehicle_value=payload.vehicle.purchase_price,
        term_months=payload.term_months,
    )

    quote = Quote(
        tenant_id=current_user.tenant_id,
        product=payload.product,
        status=QuoteStatus.QUICK_QUOTE,
        customer_name=payload.customer_name,
        term_months=payload.term_months,
        calculated_premium=premium,
        created_by=current_user.id,
    )
    db.add(quote)
    db.flush()

    vehicle = Vehicle(
        quote_id=quote.id,
        purchase_price=payload.vehicle.purchase_price,
        registration=payload.vehicle.registration,
        make=payload.vehicle.make,
        model=payload.vehicle.model,
        year=payload.vehicle.year,
        purchase_date=payload.vehicle.purchase_date,
    )
    db.add(vehicle)
    db.commit()
    db.refresh(quote)

    return quote
