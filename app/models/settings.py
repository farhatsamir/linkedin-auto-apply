from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text # type: ignore
from sqlalchemy.orm import relationship # type: ignore
from datetime import datetime
from app.database.database import Base
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text, JSON # type: ignore

class Settings(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    keywords = Column(Text, default="")          # كلمات البحث
    locations = Column(Text, default="")         # المواقع
    job_types = Column(Text, default="")         # full-time, remote...
    daily_limit = Column(Integer, default=20)    # عدد الوظائف يوميًا
    auto_apply_enabled = Column(Boolean, default=False)
    cv_summary = Column(JSON, nullable=True)
    personal_info = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="settings")
