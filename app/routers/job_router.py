from fastapi import APIRouter, Depends # type: ignore
from sqlalchemy.orm import Session # type: ignore

from app.database.database import get_db
from app.dependencies.auth_dependencies import get_current_user

from app.schemas.job_schema import JobQuestionsRequest, JobQuestionsResponse, JobAnswer
from app.services.ai_job_qa_service import AIJobQAService
from app.services.settings_service import SettingsService


router = APIRouter(
    prefix="/jobs",
    tags=["Job Intelligence"]
)


@router.post("/answer-questions", response_model=JobQuestionsResponse)
async def answer_job_questions(
    payload: JobQuestionsRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):

    # 1) جلب settings للمستخدم
    settings = SettingsService.get_user_settings(db, current_user.id)
    if not settings.cv_summary:
        return JobQuestionsResponse(answers=[])

    cv_summary = settings.cv_summary

    # 2) توليد الإجابات
    result = await AIJobQAService.generate_answers(
        job_description=payload.job_description,
        cv_summary=cv_summary,
        questions=payload.questions
    )

    # 3) تحويل النتيجة إلى Response Model
    answers = [
        JobAnswer(question=item["question"], answer=item["answer"])
        for item in result.get("answers", [])
    ]

    return JobQuestionsResponse(answers=answers)
