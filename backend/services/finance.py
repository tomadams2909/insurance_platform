from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


REPRESENTATIVE_APR = Decimal("9.9")


@dataclass
class FinanceBreakdown:
    financed_amount: Decimal    # Principal minus deposit (what the lender advances)
    monthly_payment: Decimal    # Instalment amount
    finance_charge: Decimal     # Total interest (cost of credit)
    total_repayable: Decimal    # financed_amount + finance_charge (total paid back)
    apr: Decimal                # Annual percentage rate used


def calculate_finance(
    principal: Decimal,
    deposit: Decimal,
    term_months: int,
    apr: Decimal = REPRESENTATIVE_APR,
) -> FinanceBreakdown:
    financed_amount = (principal - deposit).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    monthly_rate = apr / Decimal("12") / Decimal("100")

    # Reducing balance monthly payment formula:
    # P × r / (1 - (1 + r)^-n)
    compound = (Decimal("1") + monthly_rate) ** term_months
    monthly_payment = (
        financed_amount * monthly_rate * compound / (compound - Decimal("1"))
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    total_repayable = (monthly_payment * term_months).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    finance_charge = (total_repayable - financed_amount).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    return FinanceBreakdown(
        financed_amount=financed_amount,
        monthly_payment=monthly_payment,
        finance_charge=finance_charge,
        total_repayable=total_repayable,
        apr=apr,
    )
