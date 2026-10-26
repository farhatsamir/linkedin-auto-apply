from pydantic import BaseModel
from datetime import datetime
from typing import List

class ApplicationResponse(BaseModel):
    id: int
    user_id: int
    job_title: str | None = None
    company: str | None = None
    job_link: str | None = None
    job_description: str | None = None
    status: str
    error_message: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class ApplicationListResponse(BaseModel):
    total: int
    skip: int
    limit: int
    items: List[ApplicationResponse]