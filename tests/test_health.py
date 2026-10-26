def test_health_check_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "1.0.0"
    assert "database" in data
    assert "environment" in data


def test_home_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "LinkedIn Auto Apply API is running!"}