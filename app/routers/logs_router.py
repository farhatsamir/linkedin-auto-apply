from fastapi import APIRouter, Depends, Query  # type: ignore
from sqlalchemy.orm import Session  # type: ignore
from app.database.database import get_db
from app.dependencies.auth_dependencies import get_current_user, require_admin
from app.services.log_service import LogService
from app.schemas.logs import LogResponse, LogListResponse  # type: ignore

router = APIRouter(
    prefix="/logs",
    tags=["Logs"]
)


@router.get("/", response_model=LogListResponse)
def get_logs(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return LogService.get_user_logs(db, current_user.id, skip=skip, limit=limit)


@router.get("/level/{level}", response_model=LogListResponse)
def get_logs_by_level(
    level: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return LogService.get_logs_by_level(db, current_user.id, level, skip=skip, limit=limit)


@router.delete("/")
def delete_logs(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return LogService.delete_logs(db, current_user.id)


# ── Admin endpoints ───────────────────────────────────────────────────────────

@router.get("/admin/all", response_model=LogListResponse)
def admin_get_all_logs(
    level: str | None = Query(default=None, description="Filter by level: info, warning, error"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin)
):
    """
    Admin: view logs across all users.
    Optionally filter by level. Supports pagination.
    """
    return LogService.get_all_logs(db, level=level, skip=skip, limit=limit)