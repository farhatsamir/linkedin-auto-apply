from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime # type: ignore
from sqlalchemy.orm import relationship # type: ignore
from datetime import datetime
from app.database.database import Base

class LinkedInSession(Base):
    __tablename__ = "linkedin_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    cookies = Column(Text, nullable=True)        # ملفات الارتباط
    csrf_token = Column(String, nullable=True)   # التوكن
    user_agent = Column(String, nullable=True)   # المتصفح المستخدم
    session_data = Column(Text, nullable=True)   # أي بيانات إضافية

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="linkedin_session")
