from app.core.config import settings
from sqlalchemy import create_engine, text

engine = create_engine(settings.database_url)

with engine.connect() as conn:
    row = conn.execute(text(
        "SELECT session_data FROM linkedin_sessions LIMIT 1"
    )).fetchone()

    if row:
        value = row[0]
        print(f"Length: {len(value)}")
        print(f"Starts with: {value[:30]}")
        print(f"Is plaintext JSON: {value.strip().startswith('{')}")
        print(f"Looks encrypted: {value.startswith('gAAAAA')}")