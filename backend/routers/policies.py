import calendar
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from auth.dependencies import require_role
from database import get_db
from models.document import PolicyDocument, DocumentType
from models.policy import Policy, PolicyStatus
from models.policy_transaction import PolicyTransaction, TransactionType
from models.quote import Quote, QuoteStatus
from models.user import User, UserRole
from schemas.policy import PolicyResponse
from services.document import generate_policy_schedule

router = APIRouter(tags=["policies"])

_POLICY_ROLES = (UserRole.BROKER, UserRole.UNDERWRITER, UserRole.TENANT_ADMIN, UserRole.SUPER_ADMIN)


def _add_months(d: date, months: int) -> date:
    month = d.month + months
    year = d.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _generate_policy_number(db: Session, year: int) -> str:
    prefix = f"POL-{year}-"
    count = db.query(Policy).filter(Policy.policy_number.like(f"{prefix}%")).count()
    return f"{prefix}{str(count + 1).zfill(5)}"


@router.post("/quotes/{quote_id}/bind", response_model=PolicyResponse, status_code=201)
def bind_quote(
    quote_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_POLICY_ROLES)),
):
    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    if quote.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    if quote.status != QuoteStatus.QUOTED:
        raise HTTPException(status_code=422, detail="Only QUOTED quotes can be bound")

    today = date.today()
    inception_date = today
    expiry_date = _add_months(inception_date, quote.term_months)

    vehicle = quote.vehicle
    current_data = {
        "customer": {
            "name": quote.customer_name,
            "dob": quote.customer_dob,
            "email": quote.customer_email,
            "address": quote.customer_address,
        },
        "vehicle": {
            "registration": vehicle.registration if vehicle else None,
            "make": vehicle.make if vehicle else None,
            "model": vehicle.model if vehicle else None,
            "year": vehicle.year if vehicle else None,
            "purchase_price": str(vehicle.purchase_price) if vehicle else None,
            "purchase_date": vehicle.purchase_date if vehicle else None,
            "finance_type": vehicle.finance_type if vehicle else None,
        },
        "product": quote.product.value,
        "product_fields": quote.product_fields,
        "premium": str(quote.calculated_premium),
        "term_months": quote.term_months,
    }

    policy_number = _generate_policy_number(db, today.year)
    policy = Policy(
        quote_id=quote.id,
        tenant_id=quote.tenant_id,
        product=quote.product,
        status=PolicyStatus.BOUND,
        policy_number=policy_number,
        inception_date=inception_date,
        expiry_date=expiry_date,
        premium=quote.calculated_premium,
        current_data=current_data,
    )
    db.add(policy)
    db.flush()

    quote.status = QuoteStatus.BOUND

    transaction = PolicyTransaction(
        policy_id=policy.id,
        transaction_type=TransactionType.BIND,
        created_by=current_user.id,
        data_before=None,
        data_after=current_data,
        premium_delta=Decimal(str(quote.calculated_premium)),
    )
    db.add(transaction)
    db.commit()
    db.refresh(policy)

    return policy


@router.post("/policies/{policy_id}/issue", response_model=PolicyResponse, status_code=200)
def issue_policy(
    policy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_POLICY_ROLES)),
):
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    if policy.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    if policy.status != PolicyStatus.BOUND:
        raise HTTPException(status_code=422, detail="Only BOUND policies can be issued")

    policy.status = PolicyStatus.ISSUED

    transaction = PolicyTransaction(
        policy_id=policy.id,
        transaction_type=TransactionType.ISSUE,
        created_by=current_user.id,
        data_before=None,
        data_after=policy.current_data,
        premium_delta=None,
    )
    db.add(transaction)

    pdf_bytes = generate_policy_schedule(policy, tenant_name=policy.tenant.name)
    document = PolicyDocument(
        policy_id=policy.id,
        document_type=DocumentType.POLICY_SCHEDULE,
        filename=f"{policy.policy_number}_schedule.pdf",
        content=pdf_bytes,
    )
    db.add(document)
    db.commit()
    db.refresh(policy)

    return policy


@router.get("/policies/{policy_id}/document")
def download_policy_document(
    policy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_POLICY_ROLES)),
):
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    if policy.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    document = (
        db.query(PolicyDocument)
        .filter(
            PolicyDocument.policy_id == policy_id,
            PolicyDocument.document_type == DocumentType.POLICY_SCHEDULE,
        )
        .order_by(PolicyDocument.created_at.desc())
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="No document found for this policy")

    return Response(
        content=document.content,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={document.filename}"},
    )
