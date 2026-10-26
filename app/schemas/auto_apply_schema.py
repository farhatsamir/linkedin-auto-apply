from pydantic import BaseModel  # type: ignore
from typing import Optional
from datetime import datetime


class ContinueApplyRequest(BaseModel):
    session_id: str
    answers: dict


class ExtractQuestionsRequest(BaseModel):
    session_id: str


class AutoApplyRunResponse(BaseModel):
    id: int
    user_id: int
    status: str
    total_found: int
    applied_count: int
    failed_count: int
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AutoApplyRunListResponse(BaseModel):
    total: int
    skip: int
    limit: int
    items: list[AutoApplyRunResponse]



class ApplicationResultResponse(BaseModel):
    id: int
    job_title: Optional[str] = None
    company: Optional[str] = None
    job_link: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}