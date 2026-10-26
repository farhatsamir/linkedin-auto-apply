import json
import redis  # type: ignore
from fastapi import APIRouter, Depends, HTTPException  # type: ignore
from sqlalchemy.orm import Session  # type: ignore
from app.database.database import get_db
from app.dependencies.auth_dependencies import get_current_user
from app.services.linkedin_session_service import LinkedInSessionService
from app.schemas.linkedin_session import LinkedInSessionUpdate, LinkedInSessionResponse  # type: ignore
from app.core.config import settings
from pydantic import BaseModel  # type: ignore
from app.services.connect_token_service import create_token, redeem_token, set_status, get_status
from app.services.linkedin_session_service import LinkedInSessionService



class StorageStatePayload(BaseModel):
    token: str
    storage_state: dict



router = APIRouter(
    prefix="/linkedin-session",
    tags=["LinkedIn Session"]
)

_redis_client = redis.from_url(settings.redis_url, decode_responses=True)


@router.get("/", response_model=LinkedInSessionResponse)
def get_session(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    try:
        return LinkedInSessionService.get_session(db, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/", response_model=LinkedInSessionResponse)
def update_session(data: LinkedInSessionUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return LinkedInSessionService.create_or_update_session(
        db,
        current_user.id,
        data.dict(exclude_unset=True)
    )


@router.delete("/")
def delete_session(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return LinkedInSessionService.delete_session(db, current_user.id)






@router.post("/connect/start")
def start_connect(current_user=Depends(get_current_user)):
    """
    Called by the frontend when the user clicks "Connect LinkedIn".
    Returns a short-lived, single-use token for the Helper App to redeem.
    """
    token = create_token(current_user.id)
    return {"token": token}


@router.post("/connect/complete")
def complete_connect(payload: StorageStatePayload, db: Session = Depends(get_db)):
    """
    Called by the Helper App after it captures storage_state.
    Authenticated by the one-time token itself, not a JWT.
    """
    user_id = redeem_token(payload.token)

    if user_id is None:
        raise HTTPException(status_code=400, detail="Invalid, expired, or already-used token.")

    try:
        LinkedInSessionService.create_or_update_session(
            db,
            user_id,
            {"session_data": payload.storage_state}
        )
        set_status(payload.token, "success", "LinkedIn connected successfully.")
    except Exception as e:
        set_status(payload.token, "failed", f"Failed to save session: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save session.")

    return {"message": "LinkedIn session saved successfully."}


@router.get("/connect/status/{token}")
def get_connect_status(token: str):
    """
    Polled by the frontend to check connection progress.
    """
    return get_status(token)