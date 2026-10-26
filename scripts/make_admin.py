from app.database.database import SessionLocal
from app.models.user import User

db = SessionLocal()

user = db.query(User).filter(User.id == 1).first()

if user:
    user.role = "admin"
    db.commit()
    print("User upgraded to admin")
else:
    print("User not found")
