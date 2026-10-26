from fastapi import APIRouter, UploadFile, File, Depends  # type: ignore
from sqlalchemy.orm import Session  # type: ignore

from app.database.database import get_db
from app.dependencies.auth_dependencies import get_current_user

from app.schemas.cv_schema import CVSummaryResponse
from app.services.cv_service import CVService
from app.services.ai_summary_service import AISummaryService
from app.services.settings_service import SettingsService

router = APIRouter(
    prefix="/user",
    tags=["User CV"]
)

# ---------------------------------------------------
# 1) رفع CV → استخراج النص → تلخيصه → تخزين الملخص
# ---------------------------------------------------
@router.post("/upload-cv", response_model=CVSummaryResponse)
async def upload_and_process_cv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    user_id = current_user.id

    # 1) استخراج النص من PDF
    raw_text = await CVService.extract_text_from_pdf(file)

    # 2) تلخيص النص باستخدام Ollama
    summary_dict = await AISummaryService.summarize_cv_with_ollama(raw_text)

    SettingsService.update_settings(db, user_id, {"cv_summary": summary_dict})

    # 5) إرجاع الملخص للمستخدم
    return CVSummaryResponse(**summary_dict)
