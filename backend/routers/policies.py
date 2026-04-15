import calendar
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from auth.dependencies import require_role
from database import get_db
from models.document import PolicyDocument, DocumentType
from models.policy import Policy, PolicyStatus
from models.policy_transaction import PolicyTransaction, TransactionType
from models.quote import Quote, QuoteStatus
from models.user import User, UserRole
from schemas.policy import PolicyResponse, PolicySummaryResponse, PolicyListResponse, EndorseRequest, DocumentSummaryResponse, CancelRequest, ReinstateRequest, TransactionResponse
from services.document import generate_policy_schedule, generate_endorsement_certificate, generate_cancellation_notice, generate_reinstatement_notice

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


@router.get("/policies/{policy_id}/transactions", response_model=list[TransactionResponse])
def list_policy_transactions(
    policy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_POLICY_ROLES)),
):
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    if policy.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    transactions = (
        db.query(PolicyTransaction)
        .filter(PolicyTransaction.policy_id == policy_id)
        .order_by(PolicyTransaction.created_at.asc())
        .all()
    )

    def describe(tx) -> str:
        delta = tx.premium_delta
        tx_type = tx.transaction_type.value
        if tx_type == "BIND":
            return f"Bind — £{delta:.2f}" if delta else "Bind"
        if tx_type == "ISSUE":
            return "Issue"
        if tx_type == "ENDORSEMENT":
            return "Endorsement — no premium change"
        if tx_type == "CANCELLATION":
            return f"Cancellation — refund £{abs(delta):.2f}" if delta else "Cancellation"
        if tx_type == "REINSTATEMENT":
            return f"Reinstatement — premium due £{delta:.2f}" if delta else "Reinstatement"
        return tx_type.title()

    result = []
    for tx in transactions:
        result.append(TransactionResponse(
            id=tx.id,
            transaction_type=tx.transaction_type.value,
            created_at=tx.created_at,
            created_by=tx.created_by,
            premium_delta=tx.premium_delta,
            reason_text=tx.reason_text,
            description=describe(tx),
        ))
    return result


@router.get("/policies/{policy_id}/documents", response_model=list[DocumentSummaryResponse])
def list_policy_documents(
    policy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_POLICY_ROLES)),
):
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    if policy.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return (
        db.query(PolicyDocument)
        .filter(PolicyDocument.policy_id == policy_id)
        .order_by(PolicyDocument.created_at.asc())
        .all()
    )


@router.get("/documents/{document_id}/download")
def download_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_POLICY_ROLES)),
):
    document = db.query(PolicyDocument).filter(PolicyDocument.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.policy.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return Response(
        content=document.content,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={document.filename}"},
    )


@router.get("/policies/{policy_id}/documents/latest")
def download_latest_document(
    policy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_POLICY_ROLES)),
    document_type: Optional[str] = Query(default="POLICY_SCHEDULE", description="POLICY_SCHEDULE | ENDORSEMENT_CERTIFICATE | CANCELLATION_NOTICE"),
):
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    if policy.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        doc_type = DocumentType(document_type)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid document_type: {document_type}")

    document = (
        db.query(PolicyDocument)
        .filter(
            PolicyDocument.policy_id == policy_id,
            PolicyDocument.document_type == doc_type,
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


@router.get("/policies", response_model=PolicyListResponse)
def list_policies(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_POLICY_ROLES)),
    product: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    from models.quote import ProductType

    query = db.query(Policy)

    if current_user.role != UserRole.SUPER_ADMIN:
        query = query.filter(Policy.tenant_id == current_user.tenant_id)

    if product:
        try:
            query = query.filter(Policy.product == ProductType(product))
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid product: {product}")
    if status:
        try:
            query = query.filter(Policy.status == PolicyStatus(status))
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid status: {status}")
    if date_from:
        query = query.filter(Policy.inception_date >= date_from)
    if date_to:
        query = query.filter(Policy.inception_date <= date_to)

    total = query.count()
    items = query.order_by(Policy.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return PolicyListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/policies/{policy_id}/endorse", response_model=PolicyResponse, status_code=200)
def endorse_policy(
    policy_id: int,
    payload: EndorseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_POLICY_ROLES)),
):
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    if policy.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    if policy.status != PolicyStatus.ISSUED:
        raise HTTPException(status_code=422, detail="Only ISSUED policies can be endorsed")

    data_before = dict(policy.current_data)
    updated_data = dict(policy.current_data)
    customer = dict(updated_data.get("customer", {}))

    if "customer_name" in payload.changed_fields:
        customer["name"] = payload.changed_fields["customer_name"]
    if "customer_email" in payload.changed_fields:
        customer["email"] = payload.changed_fields["customer_email"]
    if "customer_address" in payload.changed_fields:
        customer["address"] = payload.changed_fields["customer_address"]

    updated_data["customer"] = customer
    policy.current_data = updated_data

    transaction = PolicyTransaction(
        policy_id=policy.id,
        transaction_type=TransactionType.ENDORSEMENT,
        created_by=current_user.id,
        data_before=data_before,
        data_after=updated_data,
        premium_delta=Decimal("0.00"),
        reason_text=payload.reason,
    )
    db.add(transaction)
    db.flush()

    pdf_bytes = generate_endorsement_certificate(policy, transaction, tenant_name=policy.tenant.name)
    document = PolicyDocument(
        policy_id=policy.id,
        document_type=DocumentType.ENDORSEMENT_CERTIFICATE,
        filename=f"{policy.policy_number}_endorsement_{transaction.id}.pdf",
        content=pdf_bytes,
    )
    db.add(document)
    db.commit()
    db.refresh(policy)

    return policy


@router.post("/policies/{policy_id}/cancel", response_model=PolicyResponse, status_code=200)
def cancel_policy(
    policy_id: int,
    payload: CancelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_POLICY_ROLES)),
):
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    if policy.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    if policy.status != PolicyStatus.ISSUED:
        raise HTTPException(status_code=422, detail="Only ISSUED policies can be cancelled")

    cancellation_date = payload.cancellation_date or date.today()
    if cancellation_date < policy.inception_date or cancellation_date > policy.expiry_date:
        raise HTTPException(status_code=422, detail="cancellation_date must be within the policy term")

    last_reinstatement = (
        db.query(PolicyTransaction)
        .filter(
            PolicyTransaction.policy_id == policy_id,
            PolicyTransaction.transaction_type == TransactionType.REINSTATEMENT,
        )
        .order_by(PolicyTransaction.created_at.desc())
        .first()
    )
    if last_reinstatement:
        reinstatement_date = date.fromisoformat(last_reinstatement.data_after["reinstatement_date"])
        if cancellation_date < reinstatement_date:
            raise HTTPException(
                status_code=422,
                detail=f"cancellation_date cannot be before the last reinstatement date ({reinstatement_date})",
            )

    total_days = (policy.expiry_date - policy.inception_date).days
    days_remaining = (policy.expiry_date - cancellation_date).days
    refund = (policy.premium * Decimal(days_remaining) / Decimal(total_days)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    policy.status = PolicyStatus.CANCELLED

    transaction = PolicyTransaction(
        policy_id=policy.id,
        transaction_type=TransactionType.CANCELLATION,
        created_by=current_user.id,
        data_before=policy.current_data,
        data_after={**policy.current_data, "cancellation_date": str(cancellation_date)},
        premium_delta=-refund,
        reason_text=payload.reason,
    )
    db.add(transaction)
    db.flush()

    pdf_bytes = generate_cancellation_notice(policy, transaction, tenant_name=policy.tenant.name)
    document = PolicyDocument(
        policy_id=policy.id,
        document_type=DocumentType.CANCELLATION_NOTICE,
        filename=f"{policy.policy_number}_cancellation.pdf",
        content=pdf_bytes,
    )
    db.add(document)
    db.commit()
    db.refresh(policy)

    return policy


@router.post("/policies/{policy_id}/reinstate", response_model=PolicyResponse, status_code=200)
def reinstate_policy(
    policy_id: int,
    payload: ReinstateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_POLICY_ROLES)),
):
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    if policy.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    if policy.status != PolicyStatus.CANCELLED:
        raise HTTPException(status_code=422, detail="Only CANCELLED policies can be reinstated")

    cancellation_tx = (
        db.query(PolicyTransaction)
        .filter(
            PolicyTransaction.policy_id == policy_id,
            PolicyTransaction.transaction_type == TransactionType.CANCELLATION,
        )
        .order_by(PolicyTransaction.created_at.desc())
        .first()
    )
    cancellation_date = date.fromisoformat(cancellation_tx.data_after["cancellation_date"])
    reinstatement_date = payload.reinstatement_date or date.today()

    if reinstatement_date < cancellation_date:
        raise HTTPException(
            status_code=422,
            detail=f"reinstatement_date cannot be before the cancellation date ({cancellation_date})",
        )

    days_remaining = (policy.expiry_date - cancellation_date).days
    new_expiry = reinstatement_date + timedelta(days=days_remaining)

    total_days = (policy.expiry_date - policy.inception_date).days
    reinstatement_premium = (policy.premium * Decimal(days_remaining) / Decimal(total_days)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    policy.status = PolicyStatus.ISSUED
    policy.expiry_date = new_expiry

    transaction = PolicyTransaction(
        policy_id=policy.id,
        transaction_type=TransactionType.REINSTATEMENT,
        created_by=current_user.id,
        data_before={**policy.current_data, "expiry_date": str(cancellation_tx.data_after.get("cancellation_date"))},
        data_after={**policy.current_data, "expiry_date": str(new_expiry), "reinstatement_date": str(reinstatement_date)},
        premium_delta=reinstatement_premium,
    )
    db.add(transaction)
    db.flush()

    pdf_bytes = generate_reinstatement_notice(policy, transaction, tenant_name=policy.tenant.name)
    document = PolicyDocument(
        policy_id=policy.id,
        document_type=DocumentType.REINSTATEMENT_NOTICE,
        filename=f"{policy.policy_number}_reinstatement.pdf",
        content=pdf_bytes,
    )
    db.add(document)
    db.commit()
    db.refresh(policy)

    return policy


@router.get("/policies/{policy_id}", response_model=PolicyResponse)
def get_policy(
    policy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_POLICY_ROLES)),
):
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    if current_user.role != UserRole.SUPER_ADMIN and policy.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return policy
