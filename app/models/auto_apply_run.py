from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text # type: ignore
from sqlalchemy.orm import relationship # type: ignore
from datetime import datetime
from app.database.database import Base


class AutoApplyRun(Base):
    __tablename__ = "auto_apply_runs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Run lifecycle status
    # queued | running | completed | completed_with_errors | failed
    status = Column(String, default="queued", nullable=False)

    # Progress counters
    total_found = Column(Integer, default=0)      # jobs found by search
    applied_count = Column(Integer, default=0)    # jobs successfully submitted
    failed_count = Column(Integer, default=0)     # jobs that failed

    # Error details if the entire run failed
    error_message = Column(Text, nullable=True)

    # Timestamps
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="auto_apply_runs")