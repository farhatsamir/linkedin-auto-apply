from sqlalchemy.orm import Session # type: ignore
from app.models.application import Application

class ApplicationService:
    model = Application

    @staticmethod
    def create_application(db: Session, user_id: int, data: dict):
        application = Application(
            user_id=user_id,
            run_id=data.get("run_id"),
            job_title=data.get("job_title"),
            company=data.get("company"),
            job_link=data.get("job_link"),
            job_description=data.get("job_description"),   # ← أضف هذا
            status=data.get("status", "pending"),
            error_message=data.get("error_message")
        )

        db.add(application)
        db.commit()
        db.refresh(application)
        return application

    @staticmethod
    def get_user_applications(db: Session, user_id: int, skip: int = 0, limit: int = 50):
        base_query = db.query(Application).filter(Application.user_id == user_id)
        total = base_query.count()
        items = (
            base_query
            .order_by(Application.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return {"total": total, "skip": skip, "limit": limit, "items": items}


    @staticmethod
    def get_application(db: Session, app_id: int):
        application = db.query(Application).filter(Application.id == app_id).first()
        if not application:
            raise ValueError("Application not found")
        return application

    @staticmethod
    def update_status(db: Session, app_id: int, status: str, error_message: str = None):
        application = db.query(Application).filter(Application.id == app_id).first()
        if not application:
            raise ValueError("Application not found")

        application.status = status
        if error_message:
            application.error_message = error_message

        db.commit()
        db.refresh(application)
        return application
