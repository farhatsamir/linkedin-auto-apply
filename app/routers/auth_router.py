from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException  # type: ignore
from sqlalchemy.orm import Session  # type: ignore
from jose import jwt  # type: ignore
from app.schemas.user import UserLogin, TokenResponse
from app.services.user_service import authenticate_user
from app.database.database import get_db
from app.services.jwt_service import create_access_token, revoke_token, ALGORITHM
from app.dependencies.auth_dependencies import get_current_user, oauth2_scheme
from app.core.config import settings
from fastapi.security import OAuth2PasswordBearer  # type: ignore
from fastapi import Security  # type: ignore

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


@router.post("/login", response_model=TokenResponse)
def login(user: UserLogin, db: Session = Depends(get_db)):
    try:
        authenticated_user = authenticate_user(db, user.email, user.password)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

    if not authenticated_user:
        raise HTTPException(status_code=400, detail="Invalid email or password")

    access_token = create_access_token({"sub": authenticated_user.email})
    return TokenResponse(access_token=access_token)


@router.post("/logout", status_code=200)
def logout(
    token: str = Depends(oauth2_scheme),
    current_user=Depends(get_current_user)
):
    try:
        payload = jwt.decode(token, settings.app_secret_key, algorithms=[ALGORITHM])
        jti = payload.get("jti")
        exp = payload.get("exp")

        if jti and exp:
            now = int(datetime.now(timezone.utc).timestamp())
            remaining_seconds = max(exp - now, 1)
            revoke_token(jti, remaining_seconds)

    except Exception:
        pass  # token already invalid — logout still succeeds

    return {"message": "Logged out successfully"}