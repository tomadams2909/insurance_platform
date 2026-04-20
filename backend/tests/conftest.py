import pytest
from fastapi.testclient import TestClient

from database import engine, SessionLocal
from main import app
from models.tenant import Tenant
from models.user import User, UserRole
from auth.security import get_password_hash


@pytest.fixture
def db():
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    from database import get_db
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def test_tenant(db):
    tenant = Tenant(name="Test Tenant", slug="test-tenant")
    db.add(tenant)
    db.flush()
    return tenant


@pytest.fixture
def test_user(db, test_tenant):
    user = User(
        email="test@example.com",
        hashed_password=get_password_hash("testpass123"),
        role=UserRole.BROKER,
        tenant_id=test_tenant.id,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def test_admin(db, test_tenant):
    user = User(
        email="admin@example.com",
        hashed_password=get_password_hash("testpass123"),
        role=UserRole.TENANT_ADMIN,
        tenant_id=test_tenant.id,
    )
    db.add(user)
    db.flush()
    return user
