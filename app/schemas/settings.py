from typing import Optional
from pydantic import BaseModel # type: ignore

class SettingsResponse(BaseModel):
    id: int
    user_id: int
    keywords: str | None
    locations: str | None
    job_types: str | None
    daily_limit: int
    auto_apply_enabled: bool
    cv_summary: Optional[dict] = None
    personal_info: Optional[dict] = None# ← مهم جدًا
    class Config:
        from_attributes = True

class SettingsUpdate(BaseModel):
    keywords: str | None = None
    locations: str | None = None
    job_types: str | None = None
    daily_limit: int | None = None
    auto_apply_enabled: bool | None = None
    cv_summary: Optional[dict] = None
    personal_info: Optional[dict] = None
    class Config:
        from_attributes = True