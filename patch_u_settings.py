import sys
import os
from app.db import SessionLocal
from sqlalchemy import text

db = SessionLocal()

sys.path.append(os.path.join(os.path.dirname(__file__)))


try:
    db.execute(text("""
    ALTER TABLE "USERS" ADD COLUMN settings JSON
    """
    ))
    db.commit()

except Exception as e:
    print(f"❌ Error: {e}")
    db.rollback()
    raise
finally:
    db.close()

