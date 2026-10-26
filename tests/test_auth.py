def test_register_user(client):
    response = client.post("/users/", json={
        "email": "newuser@example.com",
        "password": "password123"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert "id" in data
    assert "role" in data


def test_register_duplicate_email(client):
    client.post("/users/", json={
        "email": "duplicate@example.com",
        "password": "password123"
    })
    response = client.post("/users/", json={
        "email": "duplicate@example.com",
        "password": "password123"
    })
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]


def test_login_success(client):
    client.post("/users/", json={
        "email": "logintest@example.com",
        "password": "password123"
    })
    response = client.post("/auth/login", json={
        "email": "logintest@example.com",
        "password": "password123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client):
    client.post("/users/", json={
        "email": "wrongpass@example.com",
        "password": "correctpassword"
    })
    response = client.post("/auth/login", json={
        "email": "wrongpass@example.com",
        "password": "wrongpassword"
    })
    assert response.status_code == 400


def test_login_nonexistent_user(client):
    response = client.post("/auth/login", json={
        "email": "nobody@example.com",
        "password": "password123"
    })
    assert response.status_code == 400


def test_logout_revokes_token(client, user_token):
    # Token works before logout
    response = client.get("/users/me", headers={
        "Authorization": f"Bearer {user_token}"
    })
    assert response.status_code == 200

    # Logout
    response = client.post("/auth/logout", headers={
        "Authorization": f"Bearer {user_token}"
    })
    assert response.status_code == 200
    assert response.json()["message"] == "Logged out successfully"

    # Token is rejected after logout
    response = client.get("/users/me", headers={
        "Authorization": f"Bearer {user_token}"
    })
    assert response.status_code == 401


def test_protected_endpoint_requires_token(client):
    response = client.get("/users/me")
    assert response.status_code == 401


def test_disabled_account_cannot_login(client, db):
    from app.models.user import User
    from app.services.auth_service import hash_password

    user = User(
        email="disabled@example.com",
        password=hash_password("password123"),
        is_active=False
    )
    db.add(user)
    db.commit()

    response = client.post("/auth/login", json={
        "email": "disabled@example.com",
        "password": "password123"
    })
    assert response.status_code == 403