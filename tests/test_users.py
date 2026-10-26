def test_get_me_returns_current_user(client, user_token):
    response = client.get("/users/me", headers={
        "Authorization": f"Bearer {user_token}"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "testuser@example.com"
    assert data["role"] == "user"


def test_get_all_users_requires_admin(client, user_token):
    response = client.get("/users/", headers={
        "Authorization": f"Bearer {user_token}"
    })
    assert response.status_code == 403


def test_get_all_users_as_admin(client, admin_token):
    response = client.get("/users/", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_make_admin_requires_admin(client, user_token):
    # Create a target user first
    create = client.post("/users/", json={
        "email": "target@example.com",
        "password": "password123"
    })
    user_id = create.json()["id"]

    response = client.post(f"/users/{user_id}/make-admin", headers={
        "Authorization": f"Bearer {user_token}"
    })
    assert response.status_code == 403


def test_make_admin_as_admin(client, admin_token):
    create = client.post("/users/", json={
        "email": "promote@example.com",
        "password": "password123"
    })
    user_id = create.json()["id"]

    response = client.post(f"/users/{user_id}/make-admin", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_deactivate_user_as_admin(client, admin_token):
    create = client.post("/users/", json={
        "email": "todeactivate@example.com",
        "password": "password123"
    })
    user_id = create.json()["id"]

    response = client.post(f"/users/{user_id}/deactivate", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert response.status_code == 200

    # Deactivated user cannot login
    login = client.post("/auth/login", json={
        "email": "todeactivate@example.com",
        "password": "password123"
    })
    assert login.status_code == 403


def test_delete_user_as_admin(client, admin_token):
    create = client.post("/users/", json={
        "email": "todelete@example.com",
        "password": "password123"
    })
    user_id = create.json()["id"]

    response = client.delete(f"/users/{user_id}", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert response.status_code == 200
    assert "deleted" in response.json()["message"]


def test_delete_nonexistent_user(client, admin_token):
    response = client.delete("/users/99999", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert response.status_code == 404