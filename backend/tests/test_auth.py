from auth.security import decode_access_token


def login(client, email, password):
    return client.post("/auth/login", data={"username": email, "password": password})


def test_valid_login_returns_token(client, test_user):
    response = login(client, "test@example.com", "testpass123")
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_token_decodes_to_correct_user(client, test_user):
    response = login(client, "test@example.com", "testpass123")
    token = response.json()["access_token"]
    payload = decode_access_token(token)
    assert payload["sub"] == str(test_user.id)


def test_wrong_password_returns_401(client, test_user):
    response = login(client, "test@example.com", "wrongpassword")
    assert response.status_code == 401


def test_unknown_email_returns_401(client):
    response = login(client, "nobody@example.com", "testpass123")
    assert response.status_code == 401


def test_protected_route_without_token_returns_401(client):
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_protected_route_with_valid_token_returns_200(client, test_user):
    token = login(client, "test@example.com", "testpass123").json()["access_token"]
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"


def test_require_role_blocks_wrong_role(client, test_user, test_admin):
    from auth.dependencies import require_role
    from models.user import UserRole
    from main import app
    from fastapi import APIRouter

    router = APIRouter()

    @router.get("/test-admin-only")
    def admin_only(user=__import__('fastapi').Depends(require_role(UserRole.TENANT_ADMIN))):
        return {"ok": True}

    app.include_router(router)

    token = login(client, "test@example.com", "testpass123").json()["access_token"]
    response = client.get("/test-admin-only", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403

    admin_token = login(client, "admin@example.com", "testpass123").json()["access_token"]
    response = client.get("/test-admin-only", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
