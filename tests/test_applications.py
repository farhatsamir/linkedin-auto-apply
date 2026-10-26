from app.models.application import Application
from app.models.auto_apply_run import AutoApplyRun
from datetime import datetime


def _create_run(db, user_id):
    run = AutoApplyRun(
        user_id=user_id,
        status="completed",
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow()
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _create_application(db, user_id, run_id, title="Test Job", status="submitted"):
    app = Application(
        user_id=user_id,
        run_id=run_id,
        job_title=title,
        company="Test Company",
        status=status,
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return app


def test_get_applications_returns_paginated_response(client, user_token, db):
    # Get current user id
    me = client.get("/users/me", headers={"Authorization": f"Bearer {user_token}"})
    user_id = me.json()["id"]

    run = _create_run(db, user_id)
    for i in range(5):
        _create_application(db, user_id, run.id, title=f"Job {i}")

    response = client.get("/applications/", headers={
        "Authorization": f"Bearer {user_token}"
    })
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "skip" in data
    assert "limit" in data
    assert "items" in data
    assert data["total"] == 5
    assert len(data["items"]) == 5


def test_pagination_skip_and_limit(client, user_token, db):
    me = client.get("/users/me", headers={"Authorization": f"Bearer {user_token}"})
    user_id = me.json()["id"]

    run = _create_run(db, user_id)
    for i in range(10):
        _create_application(db, user_id, run.id, title=f"Job {i}")

    response = client.get("/applications/?skip=0&limit=3", headers={
        "Authorization": f"Bearer {user_token}"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 10
    assert len(data["items"]) == 3
    assert data["skip"] == 0
    assert data["limit"] == 3

    response2 = client.get("/applications/?skip=3&limit=3", headers={
        "Authorization": f"Bearer {user_token}"
    })
    data2 = response2.json()
    assert len(data2["items"]) == 3

    # Verify no overlap between pages
    ids_page1 = {item["id"] for item in data["items"]}
    ids_page2 = {item["id"] for item in data2["items"]}
    assert ids_page1.isdisjoint(ids_page2)


def test_applications_isolated_between_users(client, user_token, admin_token, db):
    # Get user IDs
    me = client.get("/users/me", headers={"Authorization": f"Bearer {user_token}"})
    user_id = me.json()["id"]

    admin_me = client.get("/users/me", headers={"Authorization": f"Bearer {admin_token}"})
    admin_id = admin_me.json()["id"]

    # Create applications for each user
    run1 = _create_run(db, user_id)
    run2 = _create_run(db, admin_id)
    _create_application(db, user_id, run1.id, title="User Job")
    _create_application(db, admin_id, run2.id, title="Admin Job")

    # Regular user only sees their own
    response = client.get("/applications/", headers={
        "Authorization": f"Bearer {user_token}"
    })
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["job_title"] == "User Job"


def test_get_run_results_returns_only_run_applications(client, user_token, db):
    me = client.get("/users/me", headers={"Authorization": f"Bearer {user_token}"})
    user_id = me.json()["id"]

    run1 = _create_run(db, user_id)
    run2 = _create_run(db, user_id)

    _create_application(db, user_id, run1.id, title="Run1 Job")
    _create_application(db, user_id, run2.id, title="Run2 Job")

    response = client.get(f"/auto-apply/runs/{run1.id}/results", headers={
        "Authorization": f"Bearer {user_token}"
    })
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["job_title"] == "Run1 Job"


def test_get_run_results_ownership_enforced(client, user_token, admin_token, db):
    # Admin creates a run
    admin_me = client.get("/users/me", headers={"Authorization": f"Bearer {admin_token}"})
    admin_id = admin_me.json()["id"]

    run = _create_run(db, admin_id)
    _create_application(db, admin_id, run.id, title="Admin Only Job")

    # Regular user cannot access admin's run results
    response = client.get(f"/auto-apply/runs/{run.id}/results", headers={
        "Authorization": f"Bearer {user_token}"
    })
    assert response.status_code == 403


def test_get_single_application_ownership_enforced(client, user_token, admin_token, db):
    # Admin creates an application
    admin_me = client.get("/users/me", headers={"Authorization": f"Bearer {admin_token}"})
    admin_id = admin_me.json()["id"]

    run = _create_run(db, admin_id)
    app = _create_application(db, admin_id, run.id, title="Admin App")

    # Regular user cannot access it
    response = client.get(f"/applications/{app.id}", headers={
        "Authorization": f"Bearer {user_token}"
    })
    assert response.status_code == 403