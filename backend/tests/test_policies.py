from datetime import date, timedelta, datetime
from decimal import Decimal

import pytest

from models.tenant import Tenant
from models.user import User, UserRole
from auth.security import get_password_hash

CURRENT_YEAR = datetime.now().year

FULL_QUOTE_PAYLOAD = {
    "customer_name": "Jane Smith",
    "customer_dob": "1990-05-15",
    "customer_email": "jane.smith@example.com",
    "customer_address": {"line1": "12 High Street", "city": "Manchester", "postcode": "M1 1AA"},
    "product": "GAP",
    "term_months": 36,
    "vehicle": {
        "purchase_price": 18500,
        "registration": "AB21CDE",
        "make": "Ford",
        "model": "Focus",
        "year": CURRENT_YEAR - 1,
        "purchase_date": "2024-01-10",
        "finance_type": "PCP",
    },
    "product_fields": {"settlement_figure": 15000},
}


def login(client, email, password):
    return client.post("/auth/login", data={"username": email, "password": password})


def auth_headers(client, email="test@example.com", password="testpass123"):
    token = login(client, email, password).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def quoted_quote(client, test_user):
    response = client.post("/quotes", json=FULL_QUOTE_PAYLOAD, headers=auth_headers(client))
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def bound_policy(client, test_user, quoted_quote):
    response = client.post(f"/quotes/{quoted_quote['id']}/bind", headers=auth_headers(client))
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def issued_policy(client, test_user, bound_policy):
    response = client.post(f"/policies/{bound_policy['id']}/issue", headers=auth_headers(client))
    assert response.status_code == 200
    return response.json()


@pytest.fixture
def cancelled_policy(client, test_user, issued_policy):
    cancellation_date = str(date.today() + timedelta(days=10))
    response = client.post(
        f"/policies/{issued_policy['id']}/cancel",
        json={"reason": "Test cancellation", "cancellation_date": cancellation_date},
        headers=auth_headers(client),
    )
    assert response.status_code == 200
    return response.json(), cancellation_date


# ── Bind tests ────────────────────────────────────────────────────────────────

def test_bind_returns_201_with_bound_status(client, test_user, quoted_quote):
    response = client.post(f"/quotes/{quoted_quote['id']}/bind", headers=auth_headers(client))
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "BOUND"
    assert data["policy_number"].startswith(f"POL-{date.today().year}-")
    assert data["inception_date"] == str(date.today())
    assert "current_data" in data


def test_bind_wrong_tenant_returns_403(client, db, test_user, quoted_quote):
    other_tenant = Tenant(name="Other Tenant", slug="other-tenant")
    db.add(other_tenant)
    db.flush()
    other_user = User(
        email="other@example.com",
        hashed_password=get_password_hash("testpass123"),
        role=UserRole.BROKER,
        tenant_id=other_tenant.id,
    )
    db.add(other_user)
    db.flush()
    headers = auth_headers(client, email="other@example.com")
    response = client.post(f"/quotes/{quoted_quote['id']}/bind", headers=headers)
    assert response.status_code == 403


def test_bind_non_quoted_quote_returns_422(client, test_user, bound_policy, quoted_quote):
    response = client.post(f"/quotes/{quoted_quote['id']}/bind", headers=auth_headers(client))
    assert response.status_code == 422
    assert "QUOTED" in response.json()["detail"]


# ── Issue tests ───────────────────────────────────────────────────────────────

def test_issue_transitions_to_issued(client, test_user, bound_policy):
    response = client.post(f"/policies/{bound_policy['id']}/issue", headers=auth_headers(client))
    assert response.status_code == 200
    assert response.json()["status"] == "ISSUED"


def test_issue_wrong_status_returns_422(client, test_user, issued_policy):
    response = client.post(f"/policies/{issued_policy['id']}/issue", headers=auth_headers(client))
    assert response.status_code == 422
    assert "cannot be issued" in response.json()["detail"]


# ── Endorse tests ─────────────────────────────────────────────────────────────

def test_endorse_updates_customer_name(client, test_user, issued_policy):
    response = client.post(
        f"/policies/{issued_policy['id']}/endorse",
        json={"changed_fields": {"customer_name": "Jane Updated"}, "reason": "Name correction"},
        headers=auth_headers(client),
    )
    assert response.status_code == 200
    assert response.json()["current_data"]["customer"]["name"] == "Jane Updated"


def test_endorse_locked_field_returns_422(client, test_user, issued_policy):
    response = client.post(
        f"/policies/{issued_policy['id']}/endorse",
        json={"changed_fields": {"vehicle.registration": "ZZ99ZZZ"}},
        headers=auth_headers(client),
    )
    assert response.status_code == 422
    assert "locked" in response.json()["detail"][0]["msg"]


def test_endorse_non_issued_policy_returns_422(client, test_user, bound_policy):
    response = client.post(
        f"/policies/{bound_policy['id']}/endorse",
        json={"changed_fields": {"customer_name": "Test"}},
        headers=auth_headers(client),
    )
    assert response.status_code == 422
    assert "cannot be endorsed" in response.json()["detail"]


# ── Cancel tests ──────────────────────────────────────────────────────────────

def test_cancel_returns_cancelled_with_refund(client, test_user, issued_policy):
    cancellation_date = date.today() + timedelta(days=30)
    response = client.post(
        f"/policies/{issued_policy['id']}/cancel",
        json={"reason": "Customer request", "cancellation_date": str(cancellation_date)},
        headers=auth_headers(client),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "CANCELLED"

    transactions = client.get(
        f"/policies/{issued_policy['id']}/transactions",
        headers=auth_headers(client),
    ).json()
    cancel_tx = next(t for t in transactions if t["transaction_type"] == "CANCELLATION")
    assert Decimal(cancel_tx["premium_delta"]) < 0


def test_cancel_before_inception_returns_422(client, test_user, issued_policy):
    yesterday = str(date.today() - timedelta(days=1))
    response = client.post(
        f"/policies/{issued_policy['id']}/cancel",
        json={"reason": "test", "cancellation_date": yesterday},
        headers=auth_headers(client),
    )
    assert response.status_code == 422


def test_cancel_before_reinstatement_date_returns_422(client, test_user, issued_policy):
    cancellation_date = date.today() + timedelta(days=10)
    client.post(
        f"/policies/{issued_policy['id']}/cancel",
        json={"reason": "test", "cancellation_date": str(cancellation_date)},
        headers=auth_headers(client),
    )
    reinstatement_date = date.today() + timedelta(days=20)
    client.post(
        f"/policies/{issued_policy['id']}/reinstate",
        json={"reinstatement_date": str(reinstatement_date)},
        headers=auth_headers(client),
    )
    before_reinstatement = str(date.today() + timedelta(days=15))
    response = client.post(
        f"/policies/{issued_policy['id']}/cancel",
        json={"reason": "test", "cancellation_date": before_reinstatement},
        headers=auth_headers(client),
    )
    assert response.status_code == 422
    assert "reinstatement" in response.json()["detail"].lower()


def test_cancel_non_issued_policy_returns_422(client, test_user, bound_policy):
    response = client.post(
        f"/policies/{bound_policy['id']}/cancel",
        json={"reason": "test"},
        headers=auth_headers(client),
    )
    assert response.status_code == 422
    assert "cannot be cancelled" in response.json()["detail"]


# ── Reinstate tests ───────────────────────────────────────────────────────────

def test_reinstate_returns_issued_with_new_expiry(client, test_user, cancelled_policy):
    policy, cancellation_date = cancelled_policy
    reinstatement_date = date.today() + timedelta(days=20)
    response = client.post(
        f"/policies/{policy['id']}/reinstate",
        json={"reinstatement_date": str(reinstatement_date)},
        headers=auth_headers(client),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ISSUED"
    original_expiry = date.fromisoformat(policy["expiry_date"])
    days_remaining = (original_expiry - date.fromisoformat(cancellation_date)).days
    expected_expiry = reinstatement_date + timedelta(days=days_remaining)
    assert data["expiry_date"] == str(expected_expiry)


def test_reinstate_before_cancellation_date_returns_422(client, test_user, cancelled_policy):
    policy, cancellation_date = cancelled_policy
    before_cancellation = str(date.fromisoformat(cancellation_date) - timedelta(days=1))
    response = client.post(
        f"/policies/{policy['id']}/reinstate",
        json={"reinstatement_date": before_cancellation},
        headers=auth_headers(client),
    )
    assert response.status_code == 422
    assert "cancellation date" in response.json()["detail"].lower()


def test_reinstate_non_cancelled_policy_returns_422(client, test_user, issued_policy):
    response = client.post(
        f"/policies/{issued_policy['id']}/reinstate",
        json={},
        headers=auth_headers(client),
    )
    assert response.status_code == 422
    assert "cannot be reinstated" in response.json()["detail"]


# ── Transaction history tests ─────────────────────────────────────────────────

def test_transaction_history_returns_correct_entries(client, test_user, issued_policy):
    transactions = client.get(
        f"/policies/{issued_policy['id']}/transactions",
        headers=auth_headers(client),
    ).json()
    assert len(transactions) == 2
    assert transactions[0]["transaction_type"] == "BIND"
    assert transactions[1]["transaction_type"] == "ISSUE"
    assert "description" in transactions[0]
    assert "Bind" in transactions[0]["description"]


# ── Policy list and detail tests ──────────────────────────────────────────────

def test_policy_list_returns_only_tenant_policies(client, db, test_user, bound_policy):
    other_tenant = Tenant(name="Other Tenant", slug="other-tenant-2")
    db.add(other_tenant)
    db.flush()
    other_user = User(
        email="other2@example.com",
        hashed_password=get_password_hash("testpass123"),
        role=UserRole.BROKER,
        tenant_id=other_tenant.id,
    )
    db.add(other_user)
    db.flush()

    response = client.get("/policies", headers=auth_headers(client, email="other2@example.com"))
    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_get_policy_wrong_tenant_returns_403(client, db, test_user, bound_policy):
    other_tenant = Tenant(name="Other Tenant", slug="other-tenant-3")
    db.add(other_tenant)
    db.flush()
    other_user = User(
        email="other3@example.com",
        hashed_password=get_password_hash("testpass123"),
        role=UserRole.BROKER,
        tenant_id=other_tenant.id,
    )
    db.add(other_user)
    db.flush()

    response = client.get(
        f"/policies/{bound_policy['id']}",
        headers=auth_headers(client, email="other3@example.com"),
    )
    assert response.status_code == 403


def test_get_policy_not_found_returns_404(client, test_user):
    response = client.get("/policies/999999", headers=auth_headers(client))
    assert response.status_code == 404


# ── Full lifecycle test ───────────────────────────────────────────────────────

def test_full_policy_lifecycle(client, test_user, quoted_quote):
    # Bind
    policy = client.post(
        f"/quotes/{quoted_quote['id']}/bind", headers=auth_headers(client)
    ).json()
    assert policy["status"] == "BOUND"
    policy_id = policy["id"]

    # Issue
    policy = client.post(f"/policies/{policy_id}/issue", headers=auth_headers(client)).json()
    assert policy["status"] == "ISSUED"

    # Endorse
    policy = client.post(
        f"/policies/{policy_id}/endorse",
        json={"changed_fields": {"customer_name": "Jane Updated"}, "reason": "Correction"},
        headers=auth_headers(client),
    ).json()
    assert policy["current_data"]["customer"]["name"] == "Jane Updated"

    # Cancel
    cancellation_date = str(date.today() + timedelta(days=30))
    policy = client.post(
        f"/policies/{policy_id}/cancel",
        json={"reason": "Customer request", "cancellation_date": cancellation_date},
        headers=auth_headers(client),
    ).json()
    assert policy["status"] == "CANCELLED"

    # Reinstate
    reinstatement_date = str(date.today() + timedelta(days=40))
    policy = client.post(
        f"/policies/{policy_id}/reinstate",
        json={"reinstatement_date": reinstatement_date},
        headers=auth_headers(client),
    ).json()
    assert policy["status"] == "ISSUED"

    # Verify full transaction history
    transactions = client.get(
        f"/policies/{policy_id}/transactions", headers=auth_headers(client)
    ).json()
    types = [t["transaction_type"] for t in transactions]
    assert types == ["BIND", "ISSUE", "ENDORSEMENT", "CANCELLATION", "REINSTATEMENT"]


# ── Policy detail tests ───────────────────────────────────────────────────────

def test_get_policy_detail_returns_policy_data(client, test_user, issued_policy):
    response = client.get(f"/policies/{issued_policy['id']}", headers=auth_headers(client))
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == issued_policy["id"]
    assert data["status"] == "ISSUED"
    assert data["policy_number"].startswith(f"POL-{date.today().year}-")
    assert data["current_data"]["customer"]["name"] == "Jane Smith"


# ── Endorsement premium delta ─────────────────────────────────────────────────

def test_endorse_records_zero_premium_delta(client, test_user, issued_policy):
    client.post(
        f"/policies/{issued_policy['id']}/endorse",
        json={"changed_fields": {"customer_name": "Jane Updated"}, "reason": "Name correction"},
        headers=auth_headers(client),
    )
    transactions = client.get(
        f"/policies/{issued_policy['id']}/transactions",
        headers=auth_headers(client),
    ).json()
    endorse_tx = next(t for t in transactions if t["transaction_type"] == "ENDORSEMENT")
    assert Decimal(endorse_tx["premium_delta"]) == Decimal("0.00")


# ── Document tests ────────────────────────────────────────────────────────────

def test_list_documents_after_issue_returns_policy_schedule(client, test_user, issued_policy):
    response = client.get(
        f"/policies/{issued_policy['id']}/documents",
        headers=auth_headers(client),
    )
    assert response.status_code == 200
    docs = response.json()
    assert len(docs) == 1
    assert docs[0]["document_type"] == "POLICY_SCHEDULE"
    assert issued_policy["policy_number"] in docs[0]["filename"]


def test_list_documents_after_cancel_has_cancellation_notice(client, test_user, cancelled_policy):
    policy, _ = cancelled_policy
    response = client.get(
        f"/policies/{policy['id']}/documents",
        headers=auth_headers(client),
    )
    assert response.status_code == 200
    doc_types = [d["document_type"] for d in response.json()]
    assert "POLICY_SCHEDULE" in doc_types
    assert "CANCELLATION_NOTICE" in doc_types


def test_download_document_by_id_returns_pdf(client, test_user, issued_policy):
    docs = client.get(
        f"/policies/{issued_policy['id']}/documents",
        headers=auth_headers(client),
    ).json()
    doc_id = docs[0]["id"]
    response = client.get(f"/documents/{doc_id}/download", headers=auth_headers(client))
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert len(response.content) > 0


def test_download_latest_policy_schedule(client, test_user, issued_policy):
    response = client.get(
        f"/policies/{issued_policy['id']}/documents/latest",
        params={"document_type": "POLICY_SCHEDULE"},
        headers=auth_headers(client),
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"


def test_download_latest_document_invalid_type_returns_422(client, test_user, issued_policy):
    response = client.get(
        f"/policies/{issued_policy['id']}/documents/latest",
        params={"document_type": "INVALID_TYPE"},
        headers=auth_headers(client),
    )
    assert response.status_code == 422


def test_list_documents_wrong_tenant_returns_403(client, db, test_user, issued_policy):
    other_tenant = Tenant(name="Other Tenant", slug="other-docs-tenant")
    db.add(other_tenant)
    db.flush()
    other_user = User(
        email="otherdocs@example.com",
        hashed_password=get_password_hash("testpass123"),
        role=UserRole.BROKER,
        tenant_id=other_tenant.id,
    )
    db.add(other_user)
    db.flush()
    response = client.get(
        f"/policies/{issued_policy['id']}/documents",
        headers=auth_headers(client, email="otherdocs@example.com"),
    )
    assert response.status_code == 403


def test_download_document_not_found_returns_404(client, test_user):
    response = client.get("/documents/999999/download", headers=auth_headers(client))
    assert response.status_code == 404


# ── Commission tests ──────────────────────────────────────────────────────────

def test_bind_stores_commission_on_policy(client, test_user, quoted_quote):
    policy = client.post(
        f"/quotes/{quoted_quote['id']}/bind",
        headers=auth_headers(client),
    ).json()

    # broker_commission should be 15% of the premium (test_tenant default)
    premium = Decimal(str(policy["premium"]))
    expected_broker = (premium * Decimal("15") / Decimal("100")).quantize(Decimal("0.01"))
    assert Decimal(str(policy["broker_commission"])) == expected_broker
    # No dealer on test_user so dealer_fee should be zero
    assert Decimal(str(policy["dealer_fee"])) == Decimal("0.00")


def test_policy_schedule_pdf_contains_fee_disclosure(client, test_user, issued_policy):
    response = client.get(
        f"/policies/{issued_policy['id']}/documents/latest",
        params={"document_type": "POLICY_SCHEDULE"},
        headers=auth_headers(client),
    )
    assert response.status_code == 200
    assert b"Fee Disclosure" in response.content
