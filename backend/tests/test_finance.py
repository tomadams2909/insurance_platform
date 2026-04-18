from datetime import datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from main import app
from models.tenant import Tenant
from models.user import User, UserRole
from auth.security import get_password_hash
from services.finance import calculate_finance, REPRESENTATIVE_APR, FinanceBreakdown

CURRENT_YEAR = datetime.now().year

# ── Finance service unit tests ────────────────────────────────────────────────

def test_basic_finance_breakdown():
    result = calculate_finance(
        principal=Decimal("1000.00"),
        deposit=Decimal("100.00"),
        term_months=12,
        apr=Decimal("9.9"),
    )
    assert result.financed_amount == Decimal("900.00")
    assert result.finance_charge > Decimal("0")
    assert result.total_repayable > Decimal("900.00")


def test_monthly_payments_sum_to_total_repayable():
    result = calculate_finance(
        principal=Decimal("1000.00"),
        deposit=Decimal("100.00"),
        term_months=12,
        apr=Decimal("9.9"),
    )
    assert result.monthly_payment * 12 == result.total_repayable


def test_finance_charge_equals_total_repayable_minus_financed_amount():
    result = calculate_finance(
        principal=Decimal("1000.00"),
        deposit=Decimal("100.00"),
        term_months=12,
        apr=Decimal("9.9"),
    )
    assert result.finance_charge == result.total_repayable - result.financed_amount


def test_zero_deposit_financed_amount_equals_principal():
    result = calculate_finance(
        principal=Decimal("1000.00"),
        deposit=Decimal("0.00"),
        term_months=12,
        apr=Decimal("9.9"),
    )
    assert result.financed_amount == Decimal("1000.00")


def test_finance_charge_always_positive():
    result = calculate_finance(
        principal=Decimal("5000.00"),
        deposit=Decimal("500.00"),
        term_months=24,
        apr=REPRESENTATIVE_APR,
    )
    assert result.finance_charge > Decimal("0")


def test_representative_apr_stored_on_result():
    result = calculate_finance(
        principal=Decimal("2000.00"),
        deposit=Decimal("200.00"),
        term_months=12,
    )
    assert result.apr == REPRESENTATIVE_APR


def test_custom_apr_used():
    result = calculate_finance(
        principal=Decimal("1000.00"),
        deposit=Decimal("0.00"),
        term_months=12,
        apr=Decimal("19.9"),
    )
    default_result = calculate_finance(
        principal=Decimal("1000.00"),
        deposit=Decimal("0.00"),
        term_months=12,
        apr=REPRESENTATIVE_APR,
    )
    assert result.monthly_payment > default_result.monthly_payment
    assert result.finance_charge > default_result.finance_charge


def test_longer_term_produces_higher_finance_charge():
    result_12 = calculate_finance(Decimal("1000"), Decimal("0"), 12)
    result_36 = calculate_finance(Decimal("1000"), Decimal("0"), 36)
    assert result_36.finance_charge > result_12.finance_charge


def test_longer_term_produces_lower_monthly_payment():
    result_12 = calculate_finance(Decimal("1000"), Decimal("0"), 12)
    result_36 = calculate_finance(Decimal("1000"), Decimal("0"), 36)
    assert result_36.monthly_payment < result_12.monthly_payment


def test_money_values_rounded_to_2dp():
    result = calculate_finance(Decimal("999.99"), Decimal("123.45"), 12)
    for value in (result.financed_amount, result.monthly_payment, result.finance_charge, result.total_repayable):
        assert value == value.quantize(Decimal("0.01"))


def test_returns_finance_breakdown_instance():
    result = calculate_finance(Decimal("1000"), Decimal("0"), 12)
    assert isinstance(result, FinanceBreakdown)


# ── Shared helpers ────────────────────────────────────────────────────────────

_BASE_QUOTE = {
    "customer_name": "Jane Smith",
    "customer_dob": "1990-05-15",
    "customer_email": "jane.smith@example.com",
    "customer_address": {"line1": "1 High Street", "city": "Manchester", "postcode": "M1 1AA"},
    "product": "GAP",
    "term_months": 12,
    "vehicle": {
        "purchase_price": 18500,
        "registration": "AB21CDE",
        "make": "Ford",
        "model": "Focus",
        "year": CURRENT_YEAR - 1,
        "purchase_date": "2024-01-10",
        "finance_type": "PCP",
    },
    "product_fields": {"loan_amount": 15000},
}

_FINANCE_FIELDS = {
    "payment_type": "FINANCE",
    "finance_deposit": 50.00,
    "finance_term_months": 12,
}


def _auth_headers(client):
    token = client.post(
        "/auth/login", data={"username": "test@example.com", "password": "testpass123"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ── Quote endpoint tests ──────────────────────────────────────────────────────

def test_finance_quote_missing_deposit_returns_422(client, test_user):
    payload = {**_BASE_QUOTE, "payment_type": "FINANCE", "finance_term_months": 12}
    response = client.post("/quotes", json=payload, headers=_auth_headers(client))
    assert response.status_code == 422


def test_finance_quote_missing_term_months_returns_422(client, test_user):
    payload = {**_BASE_QUOTE, "payment_type": "FINANCE", "finance_deposit": 50.0}
    response = client.post("/quotes", json=payload, headers=_auth_headers(client))
    assert response.status_code == 422


def test_finance_quote_deposit_exceeds_premium_returns_422(client, test_user):
    payload = {**_BASE_QUOTE, "payment_type": "FINANCE", "finance_deposit": 99999.00, "finance_term_months": 12}
    response = client.post("/quotes", json=payload, headers=_auth_headers(client))
    assert response.status_code == 422


def test_finance_quote_returns_breakdown(client, test_user):
    payload = {**_BASE_QUOTE, **_FINANCE_FIELDS}
    response = client.post("/quotes", json=payload, headers=_auth_headers(client))
    assert response.status_code == 201
    data = response.json()
    assert data["payment_type"] == "FINANCE"
    fb = data["finance_breakdown"]
    assert fb is not None
    for key in ("financed_amount", "monthly_payment", "finance_charge", "total_repayable", "apr"):
        assert key in fb


def test_cash_quote_has_no_finance_breakdown(client, test_user):
    response = client.post("/quotes", json=_BASE_QUOTE, headers=_auth_headers(client))
    assert response.status_code == 201
    data = response.json()
    assert data["payment_type"] == "CASH"
    assert data["finance_breakdown"] is None


# ── Finance agreement endpoint ────────────────────────────────────────────────

def test_finance_agreement_endpoint_returns_pdf(client, test_user):
    response = client.post("/internal/finance/agreement", json={
        "policy_number": "POL-TEST-00001",
        "customer_name": "Jane Smith",
        "customer_address": "1 High Street, Manchester, M1 1AA",
        "vehicle_registration": "AB21CDE",
        "finance_company_name": "AutoFinance Ltd",
        "financed_amount": 850.00,
        "deposit": 50.00,
        "monthly_payment": 74.50,
        "finance_charge": 44.00,
        "total_repayable": 894.00,
        "apr": 9.9,
        "term_months": 12,
    })
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert len(response.content) > 0


# ── Financed policy issue flow ────────────────────────────────────────────────

def _create_financed_policy(client):
    headers = _auth_headers(client)
    quote = client.post("/quotes", json={**_BASE_QUOTE, **_FINANCE_FIELDS}, headers=headers).json()
    policy = client.post(f"/quotes/{quote['id']}/bind", headers=headers).json()
    issued = client.post(f"/policies/{policy['id']}/issue", headers=headers).json()
    return issued, headers


def test_financed_policy_issue_produces_two_documents(client, test_user):
    policy, headers = _create_financed_policy(client)
    docs = client.get(f"/policies/{policy['id']}/documents", headers=headers).json()
    assert len(docs) == 2
    types = {d["document_type"] for d in docs}
    assert "POLICY_SCHEDULE" in types
    assert "FINANCE_AGREEMENT" in types


def test_cash_policy_issue_produces_one_document(client, test_user):
    headers = _auth_headers(client)
    quote = client.post("/quotes", json=_BASE_QUOTE, headers=headers).json()
    policy = client.post(f"/quotes/{quote['id']}/bind", headers=headers).json()
    issued = client.post(f"/policies/{policy['id']}/issue", headers=headers).json()
    docs = client.get(f"/policies/{issued['id']}/documents", headers=headers).json()
    assert len(docs) == 1
    assert docs[0]["document_type"] == "POLICY_SCHEDULE"


# ── Policy schedule PDF content ───────────────────────────────────────────────

def test_financed_policy_schedule_contains_finance_strings(client, test_user):
    policy, headers = _create_financed_policy(client)
    docs = client.get(f"/policies/{policy['id']}/documents", headers=headers).json()
    schedule_id = next(d["id"] for d in docs if d["document_type"] == "POLICY_SCHEDULE")
    pdf = client.get(f"/documents/{schedule_id}/download", headers=headers)
    assert b"Finance Charge" in pdf.content
    assert b"Total Repayable" in pdf.content


def test_cash_policy_schedule_excludes_finance_strings(client, test_user):
    headers = _auth_headers(client)
    quote = client.post("/quotes", json=_BASE_QUOTE, headers=headers).json()
    policy = client.post(f"/quotes/{quote['id']}/bind", headers=headers).json()
    issued = client.post(f"/policies/{policy['id']}/issue", headers=headers).json()
    docs = client.get(f"/policies/{issued['id']}/documents", headers=headers).json()
    schedule_id = docs[0]["id"]
    pdf = client.get(f"/documents/{schedule_id}/download", headers=headers)
    assert b"Finance Charge" not in pdf.content
    assert b"Total Repayable" not in pdf.content
