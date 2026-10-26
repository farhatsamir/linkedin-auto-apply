from fastapi import APIRouter, Depends, HTTPException # type: ignore
from sqlalchemy.orm import Session # type: ignore
import json

from app.database.database import get_db
from app.dependencies.auth_dependencies import get_current_user
from app.services.linkedin_session_service import LinkedInSessionService

router = APIRouter(
    prefix="/linkedin-session-file",
    tags=["LinkedIn Session"]
)

@router.post("/import")
def import_session_from_file(db: Session = Depends(get_db), current_user=Depends(get_current_user)):

    # 1) قراءة session.json
    try:
        with open("session.json", "r", encoding="utf-8") as f:
            session_data = json.load(f)
    except:
        raise HTTPException(status_code=400, detail="session.json not found")

    # 2) حفظ الجلسة داخل قاعدة البيانات
    LinkedInSessionService.create_or_update_session(
        db=db,
        user_id=current_user.id,
        data={"session_data": json.dumps(session_data)}
    )

    return {"message": "LinkedIn session imported and saved successfully"}
