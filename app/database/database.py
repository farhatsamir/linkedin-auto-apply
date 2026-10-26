from sqlalchemy import create_engine  # type: ignore
from sqlalchemy.orm import sessionmaker, declarative_base  # type: ignore
from app.core.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,   # detect and discard stale connections before use
    pool_recycle=1800,    # recycle connections every 30 minutes
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()