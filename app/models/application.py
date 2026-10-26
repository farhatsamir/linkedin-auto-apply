from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime # type: ignore
from sqlalchemy.orm import relationship # type: ignore
from datetime import datetime
from app.database.database import Base

class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    run_id = Column(Integer, ForeignKey("auto_apply_runs.id"), nullable=True, index=True)

    job_title = Column(String, nullable=True)       # عنوان الوظيفة
    company = Column(String, nullable=True)          # الشركة
    job_link = Column(Text, nullable=True)           # رابط الوظيفة
    job_description = Column(Text, nullable=True)
    status = Column(String, default="pending")       # success / failed / pending
    error_message = Column(Text, nullable=True)      # في حال فشل التقديم

    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="applications")
