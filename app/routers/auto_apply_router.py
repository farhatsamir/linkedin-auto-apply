from fastapi import APIRouter, Depends, HTTPException, Query  # type: ignore
from sqlalchemy.orm import Session  # type: ignore
from datetime import datetime

from app.database.database import get_db
from app.dependencies.auth_dependencies import get_current_user, require_admin
from app.models.auto_apply_run import AutoApplyRun
from app.models.application import Application
from app.tasks.auto_apply_task import auto_apply_task
from app.schemas.auto_apply_schema import (
    AutoApplyRunResponse,
    AutoApplyRunListResponse,
    ApplicationResultResponse,
)

router = APIRouter(
    prefix="/auto-apply",
    tags=["Auto Apply"]
)


@router.post("/start", status_code=202)
def start_auto_apply(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Enqueue an auto-apply run for the current user.
    Returns run_id immediately — Playwright runs in a Celery worker.
    Poll GET /auto-apply/runs/{run_id} for status and results.
    """
    active_run = (
        db.query(AutoApplyRun)
        .filter(
            AutoApplyRun.user_id == current_user.id,
            AutoApplyRun.status.in_(["queued", "running"])
        )
        .first()
    )
    if active_run:
        raise HTTPException(
            status_code=409,
            detail=f"A run is already active (run_id={active_run.id}, status={active_run.status}). "
                   f"Wait for it to complete before starting a new one."
        )

    run = AutoApplyRun(
        user_id=current_user.id,
        status="queued",
        started_at=datetime.utcnow()
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    auto_apply_task.delay(current_user.id, run.id)

    return {
        "run_id": run.id,
        "status": "queued",
        "message": "Auto-apply job queued. Poll /auto-apply/runs/{run_id} for status and results."
    }


@router.get("/runs/{run_id}", response_model=AutoApplyRunResponse)
def get_run_status(
    run_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Poll this endpoint to check the status of an auto-apply run.
    Returns run metadata and progress counters.
    """
    run = db.get(AutoApplyRun, run_id)

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    return run


@router.get("/runs/{run_id}/results", response_model=list[ApplicationResultResponse])
def get_run_results(
    run_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Returns all application records created during a specific run.
    Call this after the run status is 'completed' or 'completed_with_errors'.
    """
    run = db.get(AutoApplyRun, run_id)

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    applications = (
        db.query(Application)
        .filter(Application.run_id == run_id)
        .order_by(Application.created_at.desc())
        .all()
    )

    return applications


# ── Admin endpoints ───────────────────────────────────────────────────────────

@router.get("/admin/runs", response_model=AutoApplyRunListResponse)
def admin_list_runs(
    status: str | None = Query(default=None, description="Filter by status: queued, running, completed, failed"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin)
):
    """
    Admin: list all runs across all users.
    Optionally filter by status. Supports pagination.
    """
    query = db.query(AutoApplyRun)
    if status:
        query = query.filter(AutoApplyRun.status == status)

    total = query.count()
    items = (
        query
        .order_by(AutoApplyRun.started_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return {"total": total, "skip": skip, "limit": limit, "items": items}


@router.get("/admin/runs/active", response_model=list[AutoApplyRunResponse])
def admin_active_runs(
    db: Session = Depends(get_db),
    _: None = Depends(require_admin)
):
    """
    Admin: list all currently queued or running tasks.
    Use this to monitor active workers and detect stuck runs.
    """
    return (
        db.query(AutoApplyRun)
        .filter(AutoApplyRun.status.in_(["queued", "running"]))
        .order_by(AutoApplyRun.started_at.asc())
        .all()
    )


@router.post("/admin/runs/{run_id}/cancel", status_code=200)
def admin_cancel_run(
    run_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin)
):
    """
    Admin: force a run to 'failed' status.
    Use this to cancel a stuck or hung run.
    """
    run = db.get(AutoApplyRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.status in ["completed", "completed_with_errors", "failed"]:
        raise HTTPException(
            status_code=409,
            detail=f"Run {run_id} is already in terminal status: {run.status}"
        )

    run.status = "failed"
    run.error_message = "Cancelled by admin"
    run.completed_at = datetime.utcnow()
    db.commit()

    return {"message": f"Run {run_id} has been cancelled", "run_id": run_id}