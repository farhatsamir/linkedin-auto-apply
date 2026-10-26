from sqlalchemy.orm import Session  # type: ignore
from app.models.logs import Log


class LogService:

    @staticmethod
    def create_log(db: Session, user_id: int, level: str, message: str):
        log = Log(
            user_id=user_id,
            level=level,
            message=message
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log

    @staticmethod
    def get_user_logs(db: Session, user_id: int, skip: int = 0, limit: int = 50):
        base_query = db.query(Log).filter(Log.user_id == user_id)
        total = base_query.count()
        items = (
            base_query
            .order_by(Log.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return {"total": total, "skip": skip, "limit": limit, "items": items}

    @staticmethod
    def get_logs_by_level(db: Session, user_id: int, level: str, skip: int = 0, limit: int = 50):
        base_query = db.query(Log).filter(
            Log.user_id == user_id,
            Log.level == level
        )
        total = base_query.count()
        items = (
            base_query
            .order_by(Log.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return {"total": total, "skip": skip, "limit": limit, "items": items}

    @staticmethod
    def get_all_logs(db: Session, level: str | None = None, skip: int = 0, limit: int = 50):
        base_query = db.query(Log)
        if level:
            base_query = base_query.filter(Log.level == level)
        total = base_query.count()
        items = (
            base_query
            .order_by(Log.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return {"total": total, "skip": skip, "limit": limit, "items": items}

    @staticmethod
    def delete_logs(db: Session, user_id: int):
        db.query(Log).filter(Log.user_id == user_id).delete()
        db.commit()
        return {"message": "Logs deleted successfully"}