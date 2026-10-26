from pydantic import BaseModel  # type: ignore
from datetime import datetime
from typing import List


class LogResponse(BaseModel):
    id: int
    user_id: int
    level: str
    message: str
    created_at: datetime

    class Config:
        from_attributes = True


class LogListResponse(BaseModel):
    total: int
    skip: int
    limit: int
    items: List[LogResponse]