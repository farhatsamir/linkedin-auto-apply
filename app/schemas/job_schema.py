from pydantic import BaseModel # type: ignore
from typing import List, Dict

class JobQuestionsRequest(BaseModel):
    job_description: str
    questions: List[str]

class JobAnswer(BaseModel):
    question: str
    answer: str

class JobQuestionsResponse(BaseModel):
    answers: List[JobAnswer]
