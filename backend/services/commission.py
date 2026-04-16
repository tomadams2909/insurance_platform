from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.dealer import Dealer
from models.dealer_commission import DealerCommission, CommissionType
from models.quote import ProductType
from models.tenant import Tenant


@dataclass
class CommissionBreakdown:
    gross_premium: Decimal        # The insurance premium charged
    dealer_fee: Decimal           # Additive — sits outside the premium, paid by customer on top
    broker_commission: Decimal    # Deducted from premium — broker's cut, reduces net to insurer
    net_premium_to_insurer: Decimal  # gross_premium - broker_commission
    total_payable: Decimal           # gross_premium + dealer_fee (customer's total cost)


def calculate_commission(
    premium: Decimal,
    product: ProductType,
    dealer: Optional[Dealer],
    tenant: Tenant,
    db: Session,
) -> CommissionBreakdown:
    """
    Calculate the full commission breakdown for a policy premium.

    Dealer fee is ADDITIVE (outside the premium):
      total_payable = gross_premium + dealer_fee

    Broker commission is DEDUCTED from the premium (inside):
      net_premium_to_insurer = gross_premium - broker_commission

    Dealer commission resolution order:
      (1) Active product-specific rate for this dealer
      (2) Active dealer default rate (null product)
      (3) Zero — no dealer or no matching commission record
    """
    dealer_fee = Decimal("0.00")

    if dealer:
        # (1) Product-specific rate
        commission = (
            db.query(DealerCommission)
            .filter(
                DealerCommission.dealer_id == dealer.id,
                DealerCommission.product == product.value,
                DealerCommission.is_active.is_(True),
            )
            .first()
        )

        # (2) Dealer default rate (null product)
        if not commission:
            commission = (
                db.query(DealerCommission)
                .filter(
                    DealerCommission.dealer_id == dealer.id,
                    DealerCommission.product.is_(None),
                    DealerCommission.is_active.is_(True),
                )
                .first()
            )

        if commission:
            if commission.commission_type == CommissionType.PERCENTAGE:
                dealer_fee = (
                    premium * Decimal(str(commission.commission_rate)) / Decimal("100")
                ).quantize(Decimal("0.01"))
            else:  # FLAT_FEE
                dealer_fee = Decimal(str(commission.commission_rate)).quantize(Decimal("0.01"))

    broker_commission = (
        premium * Decimal(str(tenant.broker_commission_rate)) / Decimal("100")
    ).quantize(Decimal("0.01"))

    return CommissionBreakdown(
        gross_premium=premium,
        dealer_fee=dealer_fee,
        broker_commission=broker_commission,
        net_premium_to_insurer=premium - broker_commission,
        total_payable=premium + dealer_fee,
    )


def get_effective_premium(policy, db: Session) -> Decimal:
    """
    Current in-force premium = sum of BIND + ENDORSEMENT premium_delta values.
    CANCELLATION and REINSTATEMENT deltas are transactional events, not changes
    to the in-force premium, so they are excluded.
    """
    from models.policy_transaction import PolicyTransaction, TransactionType

    result = db.query(func.sum(PolicyTransaction.premium_delta)).filter(
        PolicyTransaction.policy_id == policy.id,
        PolicyTransaction.transaction_type.in_([
            TransactionType.BIND,
            TransactionType.ENDORSEMENT,
        ]),
    ).scalar()

    return Decimal(str(result or 0)).quantize(Decimal("0.01"))
