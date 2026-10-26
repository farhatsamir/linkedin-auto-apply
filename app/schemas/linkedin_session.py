from pydantic import BaseModel # type: ignore

class LinkedInSessionResponse(BaseModel):
    id: int
    user_id: int
    cookies: str | None
    csrf_token: str | None
    user_agent: str | None
    session_data: str | None

    class Config:
        from_attributes = True

class LinkedInSessionUpdate(BaseModel):
    cookies: str | None = None
    csrf_token: str | None = None
    user_agent: str | None = None
    session_data: str | None = None
