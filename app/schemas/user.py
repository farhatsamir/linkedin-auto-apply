from pydantic import BaseModel # type: ignore

class UserBase(BaseModel):
    email: str

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    role: str   # ← أضفنا الدور هنا

    class Config:
        from_attributes = True   # ← يجب أن يكون داخل UserResponse وليس UserLogin

class UserLogin(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"