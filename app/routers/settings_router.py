from fastapi import APIRouter, Depends, HTTPException # type: ignore
from sqlalchemy.orm import Session # type: ignore
from app.database.database import get_db
from app.dependencies.auth_dependencies import get_current_user
from app.services.settings_service import SettingsService
from app.schemas.settings import SettingsUpdate, SettingsResponse # type: ignore

router = APIRouter(
    prefix="/settings",
    tags=["Settings"]
)

@router.get("/", response_model=SettingsResponse)
def get_settings(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    try:
        settings = SettingsService.get_user_settings(db, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return settings

@router.put("/", response_model=SettingsResponse)
def update_settings(data: SettingsUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    updated = SettingsService.update_settings(db, current_user.id, data.dict(exclude_unset=True))
    return updated
