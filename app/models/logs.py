from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime # type: ignore
from sqlalchemy.orm import relationship # type: ignore
from datetime import datetime
from app.database.database import Base

class Log(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    level = Column(String, default="info")        # info / warning / error
    message = Column(Text, nullable=False)        # نص الرسالة
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="logs")
