from datetime import datetime

import pytest

from models.quote import Quote, QuoteStatus
from models.tenant import Tenant
from models.user import User, UserRole
from auth.security import get_password_hash

CURRENT_YEAR = datetime.now().year


def login(client, email, password):
    return client.post("/auth/login", data={"username": email, "password": password})


def auth_headers(client, email="test@example.com", password="testpass123"):
    token = login(client, email, password).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


VEHICLE_QUICK = {"purchase_price": 25000}

VEHICLE_FULL = {
    "purchase_price": 25000,
    "registration": "AB12CDE",
    "make": "Toyota",
    "model": "Corolla",
    "year": CURRENT_YEAR,
    "purchase_date": "2024-01-15",
    "finance_type": "PCP",
}


# --- Quick quote ---

def test_quick_quote_returns_201(client, test_user):
    response = client.post(
        "/quotes/quick",
        json={"customer_name": "Jane Smith", "product": "GAP", "term_months": 12, "vehicle": VEHICLE_QUICK},
        headers=auth_headers(client),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "QUICK_QUOTE"
    assert data["product"] == "GAP"
    assert data["calculated_premium"] == "940.00"


def test_quick_quote_requires_auth(client, test_user):
    response = client.post(
        "/quotes/quick",
        json={"customer_name": "Jane Smith", "product": "GAP", "term_months": 12, "vehicle": VEHICLE_QUICK},
    )
    assert response.status_code == 401


def test_quick_quote_rejects_negative_price(client, test_user):
    response = client.post(
        "/quotes/quick",
        json={"customer_name": "Jane Smith", "product": "GAP", "term_months": 12, "vehicle": {"purchase_price": -1}},
        headers=auth_headers(client),
    )
    assert response.status_code == 422


def test_quick_quote_rejects_invalid_term(client, test_user):
    response = client.post(
        "/quotes/quick",
        json={"customer_name": "Jane Smith", "product": "GAP", "term_months": 18, "vehicle": VEHICLE_QUICK},
        headers=auth_headers(client),
    )
    assert response.status_code == 422


def test_quick_quote_rejects_price_over_limit(client, test_user):
    response = client.post(
        "/quotes/quick",
        json={"customer_name": "Jane Smith", "product": "GAP", "term_months": 12, "vehicle": {"purchase_price": 200001}},
        headers=auth_headers(client),
    )
    assert response.status_code == 422


# --- Full quote ---

def test_full_quote_returns_201(client, test_user):
    response = client.post(
        "/quotes",
        json={
            "customer_name": "Jane Smith",
            "customer_email": "jane@example.com",
            "product": "GAP",
            "term_months": 12,
            "vehicle": VEHICLE_FULL,
            "product_fields": {"settlement_figure": 18000},
        },
        headers=auth_headers(client),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "QUOTED"
    assert data["vehicle"]["registration"] == "AB12CDE"
    assert data["product_fields"]["settlement_figure"] == 18000


def test_full_quote_gap_missing_settlement_figure(client, test_user):
    response = client.post(
        "/quotes",
        json={
            "customer_name": "Jane Smith",
            "product": "GAP",
            "term_months": 12,
            "vehicle": VEHICLE_FULL,
            "product_fields": {},
        },
        headers=auth_headers(client),
    )
    assert response.status_code == 422
    assert "settlement_figure" in response.json()["detail"]


def test_full_quote_rejects_invalid_email(client, test_user):
    response = client.post(
        "/quotes",
        json={
            "customer_name": "Jane Smith",
            "customer_email": "notanemail",
            "product": "GAP",
            "term_months": 12,
            "vehicle": VEHICLE_FULL,
            "product_fields": {"settlement_figure": 18000},
        },
        headers=auth_headers(client),
    )
    assert response.status_code == 422


def test_full_quote_tlp_missing_tlp_limit(client, test_user):
    response = client.post(
        "/quotes",
        json={
            "customer_name": "Jane Smith",
            "product": "TLP",
            "term_months": 12,
            "vehicle": VEHICLE_FULL,
            "product_fields": {},
        },
        headers=auth_headers(client),
    )
    assert response.status_code == 422
    assert "tlp_limit" in response.json()["detail"]


# --- Promote ---

@pytest.fixture
def quick_quote(client, test_user):
    response = client.post(
        "/quotes/quick",
        json={"customer_name": "Jane Smith", "product": "GAP", "term_months": 12, "vehicle": VEHICLE_QUICK},
        headers=auth_headers(client),
    )
    return response.json()


def test_promote_returns_quoted_status(client, test_user, quick_quote):
    response = client.post(
        f"/quotes/{quick_quote['id']}/promote",
        json={
            "vehicle": VEHICLE_FULL,
            "customer_email": "jane@example.com",
            "product_fields": {"settlement_figure": 18000},
        },
        headers=auth_headers(client),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "QUOTED"
    assert response.json()["vehicle"]["registration"] == "AB12CDE"


def test_promote_already_promoted_returns_422(client, test_user, quick_quote):
    headers = auth_headers(client)
    body = {"vehicle": VEHICLE_FULL, "product_fields": {"settlement_figure": 18000}}
    client.post(f"/quotes/{quick_quote['id']}/promote", json=body, headers=headers)
    response = client.post(f"/quotes/{quick_quote['id']}/promote", json=body, headers=headers)
    assert response.status_code == 422


def test_promote_nonexistent_quote_returns_404(client, test_user):
    response = client.post(
        "/quotes/99999/promote",
        json={"vehicle": VEHICLE_FULL, "product_fields": {"settlement_figure": 18000}},
        headers=auth_headers(client),
    )
    assert response.status_code == 404


def test_promote_wrong_tenant_returns_403(client, db, test_user, quick_quote):
    other_tenant = Tenant(name="Other Co", slug="other-co")
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

    response = client.post(
        f"/quotes/{quick_quote['id']}/promote",
        json={"vehicle": VEHICLE_FULL, "product_fields": {"settlement_figure": 18000}},
        headers=auth_headers(client, "other@example.com", "testpass123"),
    )
    assert response.status_code == 403


# --- List ---

def test_list_quotes_returns_only_tenant_quotes(client, db, test_user, test_tenant):
    other_tenant = Tenant(name="Other Co", slug="other-co-2")
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

    client.post(
        "/quotes/quick",
        json={"customer_name": "Jane Smith", "product": "GAP", "term_months": 12, "vehicle": VEHICLE_QUICK},
        headers=auth_headers(client),
    )
    client.post(
        "/quotes/quick",
        json={"customer_name": "Other Person", "product": "VRI", "term_months": 12, "vehicle": VEHICLE_QUICK},
        headers=auth_headers(client, "other2@example.com", "testpass123"),
    )

    response = client.get("/quotes", headers=auth_headers(client))
    assert response.status_code == 200
    data = response.json()
    assert all(item["customer_name"] == "Jane Smith" for item in data["items"])


def test_list_quotes_pagination(client, test_user):
    headers = auth_headers(client)
    for i in range(5):
        client.post(
            "/quotes/quick",
            json={"customer_name": f"Customer {i}", "product": "GAP", "term_months": 12, "vehicle": VEHICLE_QUICK},
            headers=headers,
        )

    response = client.get("/quotes?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["total"] >= 5
    assert data["page"] == 1
    assert data["page_size"] == 2


def test_list_quotes_filter_by_product(client, test_user):
    headers = auth_headers(client)
    client.post("/quotes/quick", json={"customer_name": "Jane", "product": "GAP", "term_months": 12, "vehicle": VEHICLE_QUICK}, headers=headers)
    client.post("/quotes/quick", json={"customer_name": "Jane", "product": "VRI", "term_months": 12, "vehicle": VEHICLE_QUICK}, headers=headers)

    response = client.get("/quotes?product=GAP", headers=headers)
    assert response.status_code == 200
    assert all(item["product"] == "GAP" for item in response.json()["items"])


def test_list_quotes_filter_by_status(client, test_user):
    headers = auth_headers(client)
    client.post("/quotes/quick", json={"customer_name": "Jane", "product": "GAP", "term_months": 12, "vehicle": VEHICLE_QUICK}, headers=headers)

    response = client.get("/quotes?status=QUICK_QUOTE", headers=headers)
    assert response.status_code == 200
    assert all(item["status"] == "QUICK_QUOTE" for item in response.json()["items"])


def test_list_quotes_invalid_product_returns_422(client, test_user):
    response = client.get("/quotes?product=INVALID", headers=auth_headers(client))
    assert response.status_code == 422


def test_list_quotes_invalid_status_returns_422(client, test_user):
    response = client.get("/quotes?status=INVALID", headers=auth_headers(client))
    assert response.status_code == 422


# --- Get single quote ---

def test_get_quote_returns_200(client, test_user, quick_quote):
    response = client.get(f"/quotes/{quick_quote['id']}", headers=auth_headers(client))
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == quick_quote["id"]
    assert data["customer_name"] == "Jane Smith"
    assert "created_at" in data
    assert "vehicle_category" in data


def test_get_quote_wrong_tenant_returns_403(client, db, test_user, quick_quote):
    other_tenant = Tenant(name="Other Co", slug="other-co-3")
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
        f"/quotes/{quick_quote['id']}",
        headers=auth_headers(client, "other3@example.com", "testpass123"),
    )
    assert response.status_code == 403


def test_get_quote_not_found_returns_404(client, test_user):
    response = client.get("/quotes/99999", headers=auth_headers(client))
    assert response.status_code == 404
