from decimal import Decimal

from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel

from services.document import generate_finance_agreement

router = APIRouter(prefix="/internal", tags=["internal"])


class FinanceAgreementRequest(BaseModel):
    policy_number: str
    customer_name: str
    customer_address: str
    vehicle_registration: str
    finance_company_name: str
    financed_amount: Decimal
    deposit: Decimal
    monthly_payment: Decimal
    finance_charge: Decimal
    total_repayable: Decimal
    apr: Decimal
    term_months: int


@router.post("/finance/agreement")
def create_finance_agreement(payload: FinanceAgreementRequest):
    pdf_bytes = generate_finance_agreement(
        policy_number=payload.policy_number,
        customer_name=payload.customer_name,
        customer_address=payload.customer_address,
        vehicle_registration=payload.vehicle_registration,
        finance_company_name=payload.finance_company_name,
        financed_amount=float(payload.financed_amount),
        deposit=float(payload.deposit),
        monthly_payment=float(payload.monthly_payment),
        finance_charge=float(payload.finance_charge),
        total_repayable=float(payload.total_repayable),
        apr=float(payload.apr),
        term_months=payload.term_months,
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=finance_agreement_{payload.policy_number}.pdf"
        },
    )
