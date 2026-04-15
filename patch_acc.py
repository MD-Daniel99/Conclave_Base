import sys
import os
import uuid

sys.path.append(os.path.join(os.path.dirname(__file__)))
from sqlalchemy import text
from app.db import SessionLocal

def gen_uuid():
    return str(uuid.uuid4())

def run_patch_accounting():
    db = SessionLocal()
    try:
        print("1. Creating accounting_custom_fields table...")
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS accounting_custom_fields (
                field_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                field_name TEXT NOT NULL UNIQUE,
                field_type VARCHAR(32) NOT NULL CHECK (field_type IN ('number', 'text')),
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        
        print("2. Adding accounting_extras column to CLIENT...")
        db.execute(text("""
            ALTER TABLE "CLIENT" 
            ADD COLUMN IF NOT EXISTS accounting_extras JSONB DEFAULT '{}'
        """))
        
        db.commit()
        print("✅ Accounting dynamic fields infrastructure created!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    run_patch_accounting()