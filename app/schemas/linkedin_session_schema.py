from pydantic import BaseModel # type: ignore

class LinkedInSessionCreate(BaseModel):
    cookies: str
    csrf_token: str
    user_agent: str
