from sqlalchemy import Column, Integer, String, Boolean # type: ignore
from sqlalchemy.orm import relationship # type: ignore
from app.database.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    role = Column(String, default="user")
    is_active = Column(Boolean, default=True)   # ← أضف هذا السطر هنا

    settings = relationship("Settings", back_populates="user", uselist=False, cascade="all, delete-orphan")
    linkedin_session = relationship("LinkedInSession", back_populates="user", uselist=False, cascade="all, delete-orphan")
    applications = relationship("Application", back_populates="user", cascade="all, delete-orphan")
    logs = relationship("Log", back_populates="user", cascade="all, delete-orphan")
    auto_apply_runs = relationship("AutoApplyRun", back_populates="user", cascade="all, delete-orphan")

