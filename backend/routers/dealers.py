from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth.dependencies import require_role
from database import get_db
from models.dealer import Dealer
from models.dealer_commission import DealerCommission
from models.user import User, UserRole
from schemas.dealer import (
    DealerCreateRequest, DealerUpdateRequest, DealerResponse, CommissionCreateRequest, CommissionResponse,
)

router = APIRouter(prefix="/dealers", tags=["dealers"])

_ADMIN_ROLES = (UserRole.TENANT_ADMIN, UserRole.SUPER_ADMIN)


def _get_dealer_or_404(dealer_id: int, current_user: User, db: Session) -> Dealer:
    dealer = db.query(Dealer).filter(Dealer.id == dealer_id).first()
    if not dealer:
        raise HTTPException(status_code=404, detail="Dealer not found")
    if current_user.role != UserRole.SUPER_ADMIN and dealer.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return dealer


@router.post("", response_model=DealerResponse, status_code=201)
def create_dealer(
    payload: DealerCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ADMIN_ROLES)),
):
    dealer = Dealer(
        tenant_id=current_user.tenant_id,
        name=payload.name,
        contact_email=payload.contact_email,
        address=payload.address,
    )
    db.add(dealer)
    db.commit()
    db.refresh(dealer)
    return dealer


@router.get("", response_model=list[DealerResponse])
def list_dealers(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ADMIN_ROLES)),
):
    query = db.query(Dealer)
    if current_user.role != UserRole.SUPER_ADMIN:
        query = query.filter(Dealer.tenant_id == current_user.tenant_id)
    return query.order_by(Dealer.id.asc()).all()


@router.get("/{dealer_id}", response_model=DealerResponse)
def get_dealer(
    dealer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ADMIN_ROLES)),
):
    return _get_dealer_or_404(dealer_id, current_user, db)


@router.patch("/{dealer_id}", response_model=DealerResponse)
def update_dealer(
    dealer_id: int,
    payload: DealerUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ADMIN_ROLES)),
):
    dealer = _get_dealer_or_404(dealer_id, current_user, db)
    if payload.name is not None:
        dealer.name = payload.name
    if payload.contact_email is not None:
        dealer.contact_email = payload.contact_email
    if payload.is_active is not None:
        dealer.is_active = payload.is_active
    db.commit()
    db.refresh(dealer)
    return dealer


@router.post("/{dealer_id}/commissions", response_model=CommissionResponse, status_code=201)
def add_commission(
    dealer_id: int,
    payload: CommissionCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ADMIN_ROLES)),
):
    dealer = _get_dealer_or_404(dealer_id, current_user, db)

    product_value = payload.product.value if payload.product else None

    # Deactivate any existing active rate for the same dealer+product
    existing = (
        db.query(DealerCommission)
        .filter(
            DealerCommission.dealer_id == dealer.id,
            DealerCommission.product == product_value,
            DealerCommission.is_active.is_(True),
        )
        .all()
    )
    for record in existing:
        record.is_active = False

    commission = DealerCommission(
        dealer_id=dealer.id,
        product=product_value,
        commission_type=payload.commission_type,
        commission_rate=payload.commission_rate,
        is_active=True,
    )
    db.add(commission)
    db.commit()
    db.refresh(commission)
    return commission


@router.delete("/{dealer_id}/commissions/{commission_id}", status_code=204)
def deactivate_commission(
    dealer_id: int,
    commission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ADMIN_ROLES)),
):
    dealer = _get_dealer_or_404(dealer_id, current_user, db)
    commission = (
        db.query(DealerCommission)
        .filter(DealerCommission.id == commission_id, DealerCommission.dealer_id == dealer.id)
        .first()
    )
    if not commission:
        raise HTTPException(status_code=404, detail="Commission not found")
    commission.is_active = False
    db.commit()
