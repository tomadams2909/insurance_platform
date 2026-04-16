import pytest

from models.dealer import Dealer
from models.tenant import Tenant
from models.user import User, UserRole
from auth.security import get_password_hash


def login(client, email, password="testpass123"):
    return client.post("/auth/login", data={"username": email, "password": password})


def auth_headers(client, email, password="testpass123"):
    token = login(client, email, password).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(client, test_admin):
    return auth_headers(client, test_admin.email)


@pytest.fixture
def broker_headers(client, test_user):
    return auth_headers(client, test_user.email)


@pytest.fixture
def other_tenant(db):
    tenant = Tenant(name="Other Tenant", slug="other-tenant")
    db.add(tenant)
    db.flush()
    return tenant


@pytest.fixture
def other_admin(db, other_tenant):
    user = User(
        email="admin@other.com",
        hashed_password=get_password_hash("testpass123"),
        role=UserRole.TENANT_ADMIN,
        tenant_id=other_tenant.id,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def other_admin_headers(client, other_admin):
    return auth_headers(client, other_admin.email)


# ── Role enforcement ──────────────────────────────────────────────────────────

class TestRoleEnforcement:
    def test_broker_cannot_list_dealers(self, client, broker_headers):
        response = client.get("/dealers", headers=broker_headers)
        assert response.status_code == 403

    def test_broker_cannot_create_dealer(self, client, broker_headers):
        response = client.post("/dealers", json={"name": "Test Garage"}, headers=broker_headers)
        assert response.status_code == 403

    def test_unauthenticated_cannot_access_dealers(self, client):
        response = client.get("/dealers")
        assert response.status_code == 401


# ── CRUD ──────────────────────────────────────────────────────────────────────

class TestCreateDealer:
    def test_admin_can_create_dealer(self, client, admin_headers):
        response = client.post(
            "/dealers",
            json={"name": "City Motors", "contact_email": "fleet@citymotors.co.uk"},
            headers=admin_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "City Motors"
        assert data["contact_email"] == "fleet@citymotors.co.uk"
        assert data["is_active"] is True
        assert data["commissions"] == []

    def test_dealer_scoped_to_current_tenant(self, client, db, test_tenant, admin_headers):
        response = client.post("/dealers", json={"name": "My Dealer"}, headers=admin_headers)
        assert response.status_code == 201
        dealer = db.query(Dealer).filter(Dealer.id == response.json()["id"]).first()
        assert dealer.tenant_id == test_tenant.id


class TestListDealers:
    def test_admin_sees_only_own_tenant_dealers(self, client, db, test_tenant, other_tenant, admin_headers):
        db.add(Dealer(tenant_id=test_tenant.id, name="Own Dealer"))
        db.add(Dealer(tenant_id=other_tenant.id, name="Other Dealer"))
        db.flush()

        response = client.get("/dealers", headers=admin_headers)
        assert response.status_code == 200
        names = [d["name"] for d in response.json()]
        assert "Own Dealer" in names
        assert "Other Dealer" not in names


class TestGetDealer:
    def test_admin_can_get_own_dealer(self, client, db, test_tenant, admin_headers):
        dealer = Dealer(tenant_id=test_tenant.id, name="Target Dealer")
        db.add(dealer)
        db.flush()

        response = client.get(f"/dealers/{dealer.id}", headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["name"] == "Target Dealer"

    def test_admin_cannot_get_other_tenant_dealer(self, client, db, other_tenant, admin_headers):
        dealer = Dealer(tenant_id=other_tenant.id, name="Foreign Dealer")
        db.add(dealer)
        db.flush()

        response = client.get(f"/dealers/{dealer.id}", headers=admin_headers)
        assert response.status_code == 403

    def test_returns_404_for_missing_dealer(self, client, admin_headers):
        response = client.get("/dealers/99999", headers=admin_headers)
        assert response.status_code == 404


class TestUpdateDealer:
    def test_admin_can_update_dealer_name(self, client, db, test_tenant, admin_headers):
        dealer = Dealer(tenant_id=test_tenant.id, name="Old Name")
        db.add(dealer)
        db.flush()

        response = client.patch(f"/dealers/{dealer.id}", json={"name": "New Name"}, headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["name"] == "New Name"

    def test_admin_can_deactivate_dealer(self, client, db, test_tenant, admin_headers):
        dealer = Dealer(tenant_id=test_tenant.id, name="Active Dealer")
        db.add(dealer)
        db.flush()

        response = client.patch(f"/dealers/{dealer.id}", json={"is_active": False}, headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["is_active"] is False


# ── Commissions ───────────────────────────────────────────────────────────────

class TestCommissions:
    @pytest.fixture
    def dealer(self, db, test_tenant):
        d = Dealer(tenant_id=test_tenant.id, name="Commission Test Dealer")
        db.add(d)
        db.flush()
        return d

    def test_add_percentage_commission(self, client, dealer, admin_headers):
        response = client.post(
            f"/dealers/{dealer.id}/commissions",
            json={"product": None, "commission_type": "PERCENTAGE", "commission_rate": 15.0},
            headers=admin_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["commission_type"] == "PERCENTAGE"
        assert float(data["commission_rate"]) == 15.0
        assert data["is_active"] is True

    def test_add_flat_fee_commission(self, client, dealer, admin_headers):
        response = client.post(
            f"/dealers/{dealer.id}/commissions",
            json={"product": "TYRE_ESSENTIAL", "commission_type": "FLAT_FEE", "commission_rate": 50.0},
            headers=admin_headers,
        )
        assert response.status_code == 201
        assert response.json()["commission_type"] == "FLAT_FEE"

    def test_adding_commission_deactivates_existing_same_product(self, client, db, dealer, admin_headers):
        # Add first rate
        client.post(
            f"/dealers/{dealer.id}/commissions",
            json={"product": None, "commission_type": "PERCENTAGE", "commission_rate": 10.0},
            headers=admin_headers,
        )
        # Add second rate for same product (null = default)
        client.post(
            f"/dealers/{dealer.id}/commissions",
            json={"product": None, "commission_type": "PERCENTAGE", "commission_rate": 15.0},
            headers=admin_headers,
        )
        # GET dealer — should only have one active commission
        response = client.get(f"/dealers/{dealer.id}", headers=admin_headers)
        active = [c for c in response.json()["commissions"] if c["is_active"]]
        assert len(active) == 1
        assert float(active[0]["commission_rate"]) == 15.0

    def test_deactivate_commission(self, client, dealer, admin_headers):
        create_resp = client.post(
            f"/dealers/{dealer.id}/commissions",
            json={"product": None, "commission_type": "PERCENTAGE", "commission_rate": 12.0},
            headers=admin_headers,
        )
        commission_id = create_resp.json()["id"]

        delete_resp = client.delete(
            f"/dealers/{dealer.id}/commissions/{commission_id}",
            headers=admin_headers,
        )
        assert delete_resp.status_code == 204

        # Commission should no longer appear as active in dealer detail
        response = client.get(f"/dealers/{dealer.id}", headers=admin_headers)
        active = [c for c in response.json()["commissions"] if c["is_active"]]
        assert len(active) == 0

    def test_commission_nested_in_dealer_response(self, client, dealer, admin_headers):
        client.post(
            f"/dealers/{dealer.id}/commissions",
            json={"product": "GAP", "commission_type": "PERCENTAGE", "commission_rate": 18.0},
            headers=admin_headers,
        )
        response = client.get(f"/dealers/{dealer.id}", headers=admin_headers)
        assert response.status_code == 200
        commissions = response.json()["commissions"]
        assert len(commissions) == 1
        assert commissions[0]["product"] == "GAP"
