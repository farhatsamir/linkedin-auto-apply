from fastapi import APIRouter, Depends, HTTPException # type: ignore
from sqlalchemy.orm import Session # type: ignore
from app.schemas.user import UserCreate, UserResponse
from app.database.database import get_db
from app.dependencies.auth_dependencies import get_current_user, require_admin
from app.models.user import User
from app.services.settings_service import SettingsService
from app.services.user_service import create_user, get_all_users, get_user_by_id, set_user_role, delete_user_by_id, set_active


router = APIRouter(
    prefix="/users",
    tags=["Users"]
)


@router.post("/", response_model=UserResponse)
def create_new_user(user: UserCreate, db: Session = Depends(get_db)):
    new_user = create_user(db, user.email, user.password)
    if new_user is None:
        raise HTTPException(status_code=400, detail="Email already registered")

    SettingsService.create_default_settings(db, new_user.id)

    return new_user


@router.get("/", dependencies=[Depends(require_admin)])
def get_users(db: Session = Depends(get_db)):
    return get_all_users(db)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/{user_id}/make-admin", dependencies=[Depends(require_admin)])
def make_admin(user_id: int, db: Session = Depends(get_db)):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return set_user_role(db, user, "admin")


@router.post("/{user_id}/unmake-admin", dependencies=[Depends(require_admin)])
def revoke_admin(user_id: int, db: Session = Depends(get_db)):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return set_user_role(db, user, "user")


@router.delete("/{user_id}", dependencies=[Depends(require_admin)])
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    delete_user_by_id(db, user)
    return {"message": "User deleted successfully"}



@router.post("/{user_id}/deactivate", dependencies=[Depends(require_admin)])
def deactivate_user(user_id: int, db: Session = Depends(get_db)):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return set_active(db, user, False)


@router.post("/{user_id}/activate", dependencies=[Depends(require_admin)])
def activate_user(user_id: int, db: Session = Depends(get_db)):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return set_active(db, user, True)