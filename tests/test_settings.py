def test_get_settings_returns_defaults(client, user_token):
    response = client.get("/settings/", headers={
        "Authorization": f"Bearer {user_token}"
    })
    assert response.status_code == 200
    data = response.json()
    assert "daily_limit" in data
    assert "keywords" in data
    assert "locations" in data
    assert data["daily_limit"] == 20  # default value from Settings model


def test_update_settings(client, user_token):
    response = client.put("/settings/", json={
        "keywords": "cybersecurity, penetration testing",
        "locations": "UAE",
        "daily_limit": 10
    }, headers={
        "Authorization": f"Bearer {user_token}"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["keywords"] == "cybersecurity, penetration testing"
    assert data["locations"] == "UAE"
    assert data["daily_limit"] == 10


def test_settings_persisted_after_update(client, user_token):
    client.put("/settings/", json={
        "keywords": "SOC analyst",
        "daily_limit": 15
    }, headers={
        "Authorization": f"Bearer {user_token}"
    })

    response = client.get("/settings/", headers={
        "Authorization": f"Bearer {user_token}"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["keywords"] == "SOC analyst"
    assert data["daily_limit"] == 15


def test_settings_isolated_between_users(client, user_token, admin_token):
    # Update user settings
    client.put("/settings/", json={
        "keywords": "user keywords",
        "daily_limit": 5
    }, headers={
        "Authorization": f"Bearer {user_token}"
    })

    # Update admin settings
    client.put("/settings/", json={
        "keywords": "admin keywords",
        "daily_limit": 50
    }, headers={
        "Authorization": f"Bearer {admin_token}"
    })

    # Verify each user sees only their own settings
    user_response = client.get("/settings/", headers={
        "Authorization": f"Bearer {user_token}"
    })
    admin_response = client.get("/settings/", headers={
        "Authorization": f"Bearer {admin_token}"
    })

    assert user_response.json()["keywords"] == "user keywords"
    assert user_response.json()["daily_limit"] == 5
    assert admin_response.json()["keywords"] == "admin keywords"
    assert admin_response.json()["daily_limit"] == 50


def test_settings_requires_authentication(client):
    response = client.get("/settings/")
    assert response.status_code == 401