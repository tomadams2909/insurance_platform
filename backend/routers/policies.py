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
from services.commission import calculate_commission, get_effective_premium
from services.document import generate_policy_schedule, generate_endorsement_certificate, generate_cancellation_notice, generate_reinstatement_notice, generate_finance_agreement
from services.policy_state_machine import validate_and_transition

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

    if quote.dealer:
        current_data["dealer"] = {"id": quote.dealer.id, "name": quote.dealer.name}

    current_data["payment_type"] = quote.payment_type.value
    if quote.finance_breakdown:
        current_data["finance_breakdown"] = quote.finance_breakdown
        current_data["finance_deposit"] = str(quote.finance_deposit)
        current_data["finance_term_months"] = quote.finance_term_months

    commission = calculate_commission(
        premium=Decimal(str(quote.calculated_premium)),
        product=quote.product,
        dealer=quote.dealer,
        tenant=quote.tenant,
        db=db,
    )

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
        dealer_fee=commission.dealer_fee,
        broker_commission=commission.broker_commission,
        current_data=current_data,
        dealer_id=quote.dealer_id,
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
        commission_data={
            "gross_premium": str(commission.gross_premium),
            "dealer_fee": str(commission.dealer_fee),
            "broker_commission": str(commission.broker_commission),
            "net_premium_to_insurer": str(commission.net_premium_to_insurer),
            "total_payable": str(commission.total_payable),
        },
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
    policy.status = validate_and_transition(policy, "issue")

    transaction = PolicyTransaction(
        policy_id=policy.id,
        transaction_type=TransactionType.ISSUE,
        created_by=current_user.id,
        data_before=None,
        data_after=policy.current_data,
        premium_delta=None,
    )
    db.add(transaction)

    effective_premium = get_effective_premium(policy, db)
    pdf_bytes = generate_policy_schedule(policy, tenant_name=policy.tenant.name, primary_colour=policy.tenant.primary_colour, logo_url=policy.tenant.logo_url, effective_premium=effective_premium)
    db.add(PolicyDocument(
        policy_id=policy.id,
        document_type=DocumentType.POLICY_SCHEDULE,
        filename=f"{policy.policy_number}_schedule.pdf",
        content=pdf_bytes,
    ))

    if policy.current_data.get("payment_type") == "FINANCE":
        fb = policy.current_data.get("finance_breakdown", {})
        customer = policy.current_data.get("customer", {})
        vehicle = policy.current_data.get("vehicle", {})
        addr = customer.get("address") or {}
        address_str = ", ".join(p for p in [addr.get("line1", ""), addr.get("city", ""), addr.get("postcode", "")] if p)
        fa_bytes = generate_finance_agreement(
            policy_number=policy.policy_number,
            customer_name=customer.get("name", ""),
            customer_address=address_str or "-",
            vehicle_registration=vehicle.get("registration") or "-",
            finance_company_name=policy.tenant.finance_company or "AutoFinance Ltd",
            financed_amount=float(fb.get("financed_amount", 0)),
            deposit=float(policy.current_data.get("finance_deposit", 0)),
            monthly_payment=float(fb.get("monthly_payment", 0)),
            finance_charge=float(fb.get("finance_charge", 0)),
            total_repayable=float(fb.get("total_repayable", 0)),
            apr=float(fb.get("apr", 0)),
            term_months=int(policy.current_data.get("finance_term_months", 12)),
        )
        db.add(PolicyDocument(
            policy_id=policy.id,
            document_type=DocumentType.FINANCE_AGREEMENT,
            filename=f"{policy.policy_number}_finance_agreement.pdf",
            content=fa_bytes,
        ))

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
        .order_by(PolicyTransaction.created_at.asc(), PolicyTransaction.id.asc())
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
            return f"Endorsement — premium change £{delta:+.2f}" if delta and delta != 0 else "Endorsement — no premium change"
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
    validate_and_transition(policy, "endorse")

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

    # Calculate commission deltas if premium is changing
    commission_data = None
    if payload.premium_delta != 0:
        old_premium = get_effective_premium(policy, db)
        new_premium = old_premium + payload.premium_delta
        old_commission = calculate_commission(old_premium, policy.product, policy.dealer, policy.tenant, db)
        new_commission = calculate_commission(new_premium, policy.product, policy.dealer, policy.tenant, db)
        commission_data = {
            "premium_delta": str(payload.premium_delta),
            "dealer_fee_delta": str(new_commission.dealer_fee - old_commission.dealer_fee),
            "broker_commission_delta": str(new_commission.broker_commission - old_commission.broker_commission),
            "net_premium_delta": str(new_commission.net_premium_to_insurer - old_commission.net_premium_to_insurer),
        }

    transaction = PolicyTransaction(
        policy_id=policy.id,
        transaction_type=TransactionType.ENDORSEMENT,
        created_by=current_user.id,
        data_before=data_before,
        data_after=updated_data,
        premium_delta=payload.premium_delta,
        reason_text=payload.reason,
        commission_data=commission_data,
    )
    db.add(transaction)
    db.flush()

    pdf_bytes = generate_endorsement_certificate(policy, transaction, tenant_name=policy.tenant.name, primary_colour=policy.tenant.primary_colour, logo_url=policy.tenant.logo_url)
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
    new_status = validate_and_transition(policy, "cancel")

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
    effective_premium = get_effective_premium(policy, db)
    refund = (effective_premium * Decimal(days_remaining) / Decimal(total_days)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    policy.status = new_status

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

    pdf_bytes = generate_cancellation_notice(policy, transaction, tenant_name=policy.tenant.name, primary_colour=policy.tenant.primary_colour, logo_url=policy.tenant.logo_url)
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
    new_status = validate_and_transition(policy, "reinstate")

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
    effective_premium = get_effective_premium(policy, db)
    reinstatement_premium = (effective_premium * Decimal(days_remaining) / Decimal(total_days)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    policy.status = new_status
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

    pdf_bytes = generate_reinstatement_notice(policy, transaction, tenant_name=policy.tenant.name, primary_colour=policy.tenant.primary_colour, logo_url=policy.tenant.logo_url)
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
