from pydantic import BaseModel # type: ignore
from typing import Optional


class WorkHistoryEntry(BaseModel):
    """
    A single work experience entry extracted from the CV.
    All date fields are integers (month = 1-12, year = YYYY).
    Null end_* fields indicate the candidate currently works there.
    """
    title: str = ""
    company: str = ""
    city: str = ""
    start_month: Optional[int] = None
    start_year: Optional[int] = None
    end_month: Optional[int] = None
    end_year: Optional[int] = None
    description: str = ""
    is_current: bool = False


class CVRawTextResponse(BaseModel):
    raw_text: str


class CVSummaryRequest(BaseModel):
    raw_text: str


class CVSummaryResponse(BaseModel):
    summary: str
    core_skills: list[str]
    experience_highlights: list[str]
    technical_skills: list[str]
    domains: list[str]
    certifications: list[str]
    work_history: list[WorkHistoryEntry] = []