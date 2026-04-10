from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models.quote import Quote, QuoteStatus, ProductType
from models.vehicle import Vehicle
from models.user import User, UserRole
from schemas.quote import QuickQuoteRequest, QuickQuoteResponse, FullQuoteRequest, FullQuoteResponse, PromoteQuoteRequest, QuoteSummaryResponse, QuoteListResponse, QuoteDetailResponse
from services.pricing import calculate_premium, PRODUCT_SCHEMAS, get_vehicle_category
from auth.dependencies import require_role

router = APIRouter(prefix="/quotes", tags=["quotes"])

_QUOTE_ROLES = (UserRole.BROKER, UserRole.UNDERWRITER, UserRole.TENANT_ADMIN, UserRole.SUPER_ADMIN)


@router.post("/quick", response_model=QuickQuoteResponse, status_code=201)
def create_quick_quote(
    payload: QuickQuoteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_QUOTE_ROLES)),
):
    vehicle_value = Decimal(str(payload.vehicle.purchase_price))
    category = get_vehicle_category(vehicle_value)
    premium = calculate_premium(
        product=payload.product.value,
        vehicle_value=vehicle_value,
        term_months=payload.term_months,
    )

    quote = Quote(
        tenant_id=current_user.tenant_id,
        product=payload.product,
        status=QuoteStatus.QUICK_QUOTE,
        customer_name=payload.customer_name,
        term_months=payload.term_months,
        vehicle_category=category,
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


@router.post("", response_model=FullQuoteResponse, status_code=201)
def create_full_quote(
    payload: FullQuoteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_QUOTE_ROLES)),
):
    schema = PRODUCT_SCHEMAS[payload.product.value]
    missing = [
        f for f in schema["required_fields"]
        if not (payload.product_fields or {}).get(f)
    ]
    if missing:
        raise HTTPException(status_code=422, detail=f"Missing required product fields: {missing}")

    vehicle_value = Decimal(str(payload.vehicle.purchase_price))
    category = get_vehicle_category(vehicle_value)
    premium = calculate_premium(
        product=payload.product.value,
        vehicle_value=vehicle_value,
        term_months=payload.term_months,
    )

    quote = Quote(
        tenant_id=current_user.tenant_id,
        product=payload.product,
        status=QuoteStatus.QUOTED,
        customer_name=payload.customer_name,
        customer_dob=payload.customer_dob,
        customer_email=payload.customer_email,
        customer_address=payload.customer_address,
        term_months=payload.term_months,
        vehicle_category=category,
        product_fields=payload.product_fields,
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
        finance_type=payload.vehicle.finance_type,
    )
    db.add(vehicle)
    db.commit()
    db.refresh(quote)

    return quote


@router.post("/{quote_id}/promote", response_model=FullQuoteResponse, status_code=200)
def promote_quote(
    quote_id: int,
    payload: PromoteQuoteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_QUOTE_ROLES)),
):
    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    if quote.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    if quote.status != QuoteStatus.QUICK_QUOTE:
        raise HTTPException(status_code=422, detail="Only QUICK_QUOTE quotes can be promoted")

    schema = PRODUCT_SCHEMAS[quote.product.value]
    missing = [
        f for f in schema["required_fields"]
        if not (payload.product_fields or {}).get(f)
    ]
    if missing:
        raise HTTPException(status_code=422, detail=f"Missing required product fields: {missing}")

    vehicle_value = Decimal(str(payload.vehicle.purchase_price))
    category = get_vehicle_category(vehicle_value)
    premium = calculate_premium(
        product=quote.product.value,
        vehicle_value=vehicle_value,
        term_months=payload.term_months or quote.term_months,
    )

    quote.status = QuoteStatus.QUOTED
    quote.vehicle_category = category
    quote.calculated_premium = premium
    if payload.customer_name:
        quote.customer_name = payload.customer_name
    if payload.customer_dob:
        quote.customer_dob = payload.customer_dob
    if payload.customer_email:
        quote.customer_email = payload.customer_email
    if payload.customer_address:
        quote.customer_address = payload.customer_address
    if payload.term_months:
        quote.term_months = payload.term_months
    if payload.product_fields:
        quote.product_fields = payload.product_fields

    vehicle = quote.vehicle
    vehicle.purchase_price = payload.vehicle.purchase_price
    vehicle.registration = payload.vehicle.registration
    vehicle.make = payload.vehicle.make
    vehicle.model = payload.vehicle.model
    vehicle.year = payload.vehicle.year
    vehicle.purchase_date = payload.vehicle.purchase_date
    vehicle.finance_type = payload.vehicle.finance_type

    db.commit()
    db.refresh(quote)

    return quote


@router.get("/{quote_id}", response_model=QuoteDetailResponse)
def get_quote(
    quote_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_QUOTE_ROLES)),
):
    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    if current_user.role != UserRole.SUPER_ADMIN and quote.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return quote


@router.get("", response_model=QuoteListResponse)
def list_quotes(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_QUOTE_ROLES)),
    product: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    query = db.query(Quote)

    if current_user.role != UserRole.SUPER_ADMIN:
        query = query.filter(Quote.tenant_id == current_user.tenant_id)

    if product:
        try:
            query = query.filter(Quote.product == ProductType(product))
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid product: {product}")
    if status:
        try:
            query = query.filter(Quote.status == QuoteStatus(status))
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid status: {status}")
    if date_from:
        query = query.filter(Quote.created_at >= date_from)
    if date_to:
        query = query.filter(Quote.created_at <= date_to)

    total = query.count()
    items = query.order_by(Quote.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return QuoteListResponse(items=items, total=total, page=page, page_size=page_size)
