from pydantic import BaseModel # type: ignore
from typing import Optional

class SettingsUpdate(BaseModel):
    keywords: Optional[str] = None
    locations: Optional[str] = None
    job_types: Optional[str] = None
    daily_limit: Optional[int] = None
    auto_apply_enabled: Optional[bool] = None
    cv_summary: Optional[dict] = None
    personal_info: Optional[dict] = None