import json
import base64
import hashlib
from cryptography.fernet import Fernet  # type: ignore
from sqlalchemy.orm import Session  # type: ignore
from app.models.linkedin_session import LinkedInSession
from app.core.config import settings


def _get_fernet() -> Fernet:
    """
    Derive a stable 32-byte Fernet key from the app secret key.
    SHA-256 of the secret gives us a consistent 32-byte key.
    Fernet requires a URL-safe base64-encoded 32-byte key.
    """
    raw_key = hashlib.sha256(settings.app_secret_key.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(raw_key)
    return Fernet(fernet_key)


def _encrypt(data: str) -> str:
    """Encrypt a string and return a base64-encoded encrypted string."""
    return _get_fernet().encrypt(data.encode()).decode()


def _decrypt(data: str) -> str:
    """Decrypt a base64-encoded encrypted string and return the original string."""
    return _get_fernet().decrypt(data.encode()).decode()


class LinkedInSessionService:

    @staticmethod
    def get_session(db: Session, user_id: int):
        session = (
            db.query(LinkedInSession)
            .filter(LinkedInSession.user_id == user_id)
            .first()
        )
        if not session:
            raise ValueError("LinkedIn session not found")
        return session

    @staticmethod
    def create_or_update_session(db: Session, user_id: int, data: dict):
        session = (
            db.query(LinkedInSession)
            .filter(LinkedInSession.user_id == user_id)
            .first()
        )

        if not session:
            session = LinkedInSession(user_id=user_id)

        for key, value in data.items():
            if hasattr(session, key):
                if key == "session_data":
                    # Encrypt session_data before storing
                    raw = json.dumps(value) if isinstance(value, (dict, list)) else value
                    setattr(session, key, _encrypt(raw))
                elif isinstance(value, (dict, list)):
                    setattr(session, key, json.dumps(value))
                else:
                    setattr(session, key, value)

        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    @staticmethod
    def delete_session(db: Session, user_id: int):
        session = (
            db.query(LinkedInSession)
            .filter(LinkedInSession.user_id == user_id)
            .first()
        )
        if not session:
            raise ValueError("Session not found")

        db.delete(session)
        db.commit()
        return {"message": "LinkedIn session deleted successfully"}

    @staticmethod
    def get_storage_state(db: Session, user_id: int) -> dict:
        session = (
            db.query(LinkedInSession)
            .filter(LinkedInSession.user_id == user_id)
            .first()
        )
        if not session:
            raise ValueError("LinkedIn session not found")

        try:
            decrypted = _decrypt(session.session_data)
            return json.loads(decrypted)
        except Exception:
            raise ValueError(
                "LinkedIn session data is invalid, corrupted, or not encrypted. "
                "Please re-import your session using POST /linkedin-session-file/import"
            )