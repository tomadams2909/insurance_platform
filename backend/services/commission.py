from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from models.dealer import Dealer
from models.dealer_commission import DealerCommission, CommissionType
from models.quote import ProductType
from models.tenant import Tenant


@dataclass
class CommissionBreakdown:
    gross_premium: Decimal
    dealer_fee: Decimal
    dealer_fee_rate: Decimal          # rate used (0 if no dealer fee)
    broker_commission: Decimal
    broker_commission_rate: Decimal   # rate used
    net_premium_to_insurer: Decimal   # gross_premium - broker_commission
    total_payable: Decimal            # gross_premium + dealer_fee (customer total)


def calculate_commission(
    premium: Decimal,
    product: ProductType,
    dealer: Optional[Dealer],
    tenant: Tenant,
    db: Session,
) -> CommissionBreakdown:
    dealer_fee = Decimal("0.00")
    dealer_fee_rate = Decimal("0.0000")

    if dealer:
        commission = (
            db.query(DealerCommission)
            .filter(
                DealerCommission.dealer_id == dealer.id,
                DealerCommission.product == product.value,
                DealerCommission.is_active.is_(True),
            )
            .first()
        )

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
            dealer_fee_rate = Decimal(str(commission.commission_rate))
            if commission.commission_type == CommissionType.PERCENTAGE:
                dealer_fee = (premium * dealer_fee_rate / Decimal("100")).quantize(Decimal("0.01"))
            else:
                dealer_fee = dealer_fee_rate.quantize(Decimal("0.01"))

    broker_commission_rate = Decimal(str(tenant.broker_commission_rate))
    broker_commission = (premium * broker_commission_rate / Decimal("100")).quantize(Decimal("0.01"))

    return CommissionBreakdown(
        gross_premium=premium,
        dealer_fee=dealer_fee,
        dealer_fee_rate=dealer_fee_rate,
        broker_commission=broker_commission,
        broker_commission_rate=broker_commission_rate,
        net_premium_to_insurer=premium - broker_commission,
        total_payable=premium + dealer_fee,
    )


def get_effective_premium(policy, db: Session) -> Decimal:
    """Current in-force premium — read directly from the policy row."""
    return Decimal(str(policy.premium)).quantize(Decimal("0.01"))
