from app.models.auto_apply_run import AutoApplyRun
from datetime import datetime
from unittest.mock import patch


def _create_run(db, user_id, status="completed"):
    run = AutoApplyRun(
        user_id=user_id,
        status=status,
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow() if status not in ["queued", "running"] else None
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def test_get_run_status(client, user_token, db):
    me = client.get("/users/me", headers={"Authorization": f"Bearer {user_token}"})
    user_id = me.json()["id"]

    run = _create_run(db, user_id, status="completed")

    response = client.get(f"/auto-apply/runs/{run.id}", headers={
        "Authorization": f"Bearer {user_token}"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == run.id
    assert data["status"] == "completed"


def test_get_run_status_ownership_enforced(client, user_token, admin_token, db):
    admin_me = client.get("/users/me", headers={"Authorization": f"Bearer {admin_token}"})
    admin_id = admin_me.json()["id"]

    run = _create_run(db, admin_id, status="completed")

    # Regular user cannot see admin's run
    response = client.get(f"/auto-apply/runs/{run.id}", headers={
        "Authorization": f"Bearer {user_token}"
    })
    assert response.status_code == 403


def test_start_run_blocked_when_active_run_exists(client, user_token, db):
    me = client.get("/users/me", headers={"Authorization": f"Bearer {user_token}"})
    user_id = me.json()["id"]

    # Create an active run directly in DB
    _create_run(db, user_id, status="running")

    # Starting a new run should be blocked
    with patch("app.routers.auto_apply_router.auto_apply_task") as mock_task:
        response = client.post("/auto-apply/start", headers={
            "Authorization": f"Bearer {user_token}"
        })

    assert response.status_code == 409
    assert "already active" in response.json()["detail"]


def test_start_run_allowed_when_no_active_run(client, user_token, db):
    me = client.get("/users/me", headers={"Authorization": f"Bearer {user_token}"})
    user_id = me.json()["id"]

    # Only completed runs exist — new run should be allowed
    _create_run(db, user_id, status="completed")

    with patch("app.routers.auto_apply_router.auto_apply_task") as mock_task:
        mock_task.delay.return_value = None
        response = client.post("/auto-apply/start", headers={
            "Authorization": f"Bearer {user_token}"
        })

    assert response.status_code == 202
    assert "run_id" in response.json()


def test_admin_list_all_runs(client, admin_token, user_token, db):
    me = client.get("/users/me", headers={"Authorization": f"Bearer {user_token}"})
    user_id = me.json()["id"]

    admin_me = client.get("/users/me", headers={"Authorization": f"Bearer {admin_token}"})
    admin_id = admin_me.json()["id"]

    _create_run(db, user_id, status="completed")
    _create_run(db, admin_id, status="completed")

    response = client.get("/auto-apply/admin/runs", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_admin_list_runs_blocked_for_regular_user(client, user_token):
    response = client.get("/auto-apply/admin/runs", headers={
        "Authorization": f"Bearer {user_token}"
    })
    assert response.status_code == 403


def test_admin_active_runs(client, admin_token, db):
    admin_me = client.get("/users/me", headers={"Authorization": f"Bearer {admin_token}"})
    admin_id = admin_me.json()["id"]

    _create_run(db, admin_id, status="running")
    _create_run(db, admin_id, status="completed")

    response = client.get("/auto-apply/admin/runs/active", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert response.status_code == 200
    runs = response.json()
    assert len(runs) == 1
    assert runs[0]["status"] == "running"


def test_admin_cancel_run(client, admin_token, db):
    admin_me = client.get("/users/me", headers={"Authorization": f"Bearer {admin_token}"})
    admin_id = admin_me.json()["id"]

    run = _create_run(db, admin_id, status="running")

    response = client.post(f"/auto-apply/admin/runs/{run.id}/cancel", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert response.status_code == 200
    assert response.json()["run_id"] == run.id

    # Verify status changed in DB
    db.refresh(run)
    assert run.status == "failed"
    assert run.error_message == "Cancelled by admin"


def test_admin_cancel_already_completed_run(client, admin_token, db):
    admin_me = client.get("/users/me", headers={"Authorization": f"Bearer {admin_token}"})
    admin_id = admin_me.json()["id"]

    run = _create_run(db, admin_id, status="completed")

    response = client.post(f"/auto-apply/admin/runs/{run.id}/cancel", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert response.status_code == 409
    assert "terminal status" in response.json()["detail"]


def test_admin_cancel_nonexistent_run(client, admin_token):
    response = client.post("/auto-apply/admin/runs/99999/cancel", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert response.status_code == 404