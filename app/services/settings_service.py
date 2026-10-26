from sqlalchemy.orm import Session # type: ignore
from app.models.settings import Settings
from app.models.user import User

class SettingsService:

    @staticmethod
    def get_user_settings(db: Session, user_id: int):
        settings = db.query(Settings).filter(Settings.user_id == user_id).first()
        if not settings:
            raise ValueError("Settings not found")
        return settings

    @staticmethod
    def create_default_settings(db: Session, user_id: int):
        existing = db.query(Settings).filter(Settings.user_id == user_id).first()
        if existing:
            return existing

        settings = Settings(
            user_id=user_id,
            keywords="",
            locations="",
            job_types="",
            daily_limit=20,
            auto_apply_enabled=False
        )

        db.add(settings)
        db.commit()
        db.refresh(settings)
        return settings

    @staticmethod
    def update_settings(db: Session, user_id: int, data: dict):
        settings = db.query(Settings).filter(Settings.user_id == user_id).first()

        # إذا لم توجد إعدادات → أنشئ واحدة جديدة
        if not settings:
            settings = Settings(user_id=user_id, **data)
            db.add(settings)
            db.commit()
            db.refresh(settings)
            return settings

        # إذا كانت موجودة → حدّثها
        for key, value in data.items():
            if hasattr(settings, key):
                setattr(settings, key, value)

        db.commit()
        db.refresh(settings)
        return settings
