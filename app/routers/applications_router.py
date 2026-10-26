from fastapi import APIRouter, Depends, HTTPException, Query  # type: ignore
from sqlalchemy.orm import Session # type: ignore
from app.database.database import get_db
from app.dependencies.auth_dependencies import get_current_user
from app.services.application_service import ApplicationService
from app.schemas.application import ApplicationResponse, ApplicationListResponse  # type: ignore


router = APIRouter(
    prefix="/applications",
    tags=["Applications"]
)


@router.get("/", response_model=ApplicationListResponse)
def get_my_applications(
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=50, ge=1, description="Maximum number of records to return"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return ApplicationService.get_user_applications(db, current_user.id, skip=skip, limit=limit)


@router.get("/{app_id}", response_model=ApplicationResponse)
def get_application(app_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    application = ApplicationService.get_application(db, app_id)

    if application.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    return application