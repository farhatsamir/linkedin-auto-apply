from sqlalchemy.orm import Session # type: ignore
from app.models.user import User
from app.services.auth_service import hash_password, verify_password


def create_user(db: Session, email: str, password: str):
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        return None

    db_user = User(
        email=email,
        password=hash_password(password)
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def authenticate_user(db: Session, email: str, password: str):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return None
    if not verify_password(password, user.password):
        return None
    if not user.is_active:
        raise ValueError("Account is disabled")
    return user


def get_all_users(db: Session):
    return db.query(User).all()


def get_user_by_id(db: Session, user_id: int):
    return db.query(User).filter(User.id == user_id).first()


def set_user_role(db: Session, user: User, role: str):
    user.role = role
    db.commit()
    db.refresh(user)
    return user


def delete_user_by_id(db: Session, user: User):
    db.delete(user)
    db.commit()


def set_active(db: Session, user: User, is_active: bool):
    user.is_active = is_active
    db.commit()
    db.refresh(user)
    return user