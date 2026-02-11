import sys
import os
import re
import uuid

# Добавляем текущую директорию в путь, чтобы Python видел папку app
sys.path.append(os.path.join(os.path.dirname(__file__)))

from sqlalchemy import text, update, delete
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app import models

def gen_uuid():
    return uuid.uuid4()

def add_columns(db: Session):
    """1. Создание таблиц справочников и колонок"""
    print("\n--- [1/4] Проверка и обновление структуры БД... ---")
    try:
        # MODULES (старые колонки)
        db.execute(text("ALTER TABLE \"MODULES\" ADD COLUMN IF NOT EXISTS size VARCHAR(64)"))
        db.execute(text("ALTER TABLE \"MODULES\" ADD COLUMN IF NOT EXISTS stiffness VARCHAR(64)"))
        db.execute(text("ALTER TABLE \"MODULES\" ADD COLUMN IF NOT EXISTS side VARCHAR(64)"))
        db.execute(text("ALTER TABLE \"MODULES\" ADD COLUMN IF NOT EXISTS prosthetist_keep VARCHAR(64)"))
        
        # CLIENT (старые колонки)
        db.execute(text("ALTER TABLE \"CLIENT\" ADD COLUMN IF NOT EXISTS ipra_code VARCHAR(64)"))
        db.execute(text("ALTER TABLE \"CLIENT\" ADD COLUMN IF NOT EXISTS place_of_residence VARCHAR(255)"))
        db.execute(text("ALTER TABLE \"CLIENT\" ADD COLUMN IF NOT EXISTS tsr_code TEXT"))
        db.execute(text("ALTER TABLE \"MODULES\" DROP COLUMN IF EXISTS tsr_code"))

        # --- ИСПРАВЛЕНИЕ СПРАВОЧНИКОВ ---
        # Удаляем старые таблицы, так как в них могли быть неправильные имена колонок (id вместо prosthesis_id)
        db.execute(text("DROP TABLE IF EXISTS \"REF_PROSTHESIS\""))
        db.execute(text("DROP TABLE IF EXISTS \"REF_TSR\""))

        # Создаем заново с правильными именами из models.py
        # 1. Prosthesis
        db.execute(text("""
            CREATE TABLE "REF_PROSTHESIS" (
                prosthesis_id UUID PRIMARY KEY,  -- Имя как в models.py
                name TEXT NOT NULL UNIQUE
            )
        """))
        db.execute(text("ALTER TABLE \"MODULES\" ALTER COLUMN module_name TYPE VARCHAR(512)"))
        
        # 2. TSR
        db.execute(text("""
            CREATE TABLE "REF_TSR" (
                tsr_id UUID PRIMARY KEY,        -- Имя как в models.py
                full_tsr_code TEXT NOT NULL UNIQUE
            )
        """))
        
        db.commit()
        print("✅ Таблицы справочников пересозданы корректно.")
    except Exception as e:
        print(f"❌ Ошибка структуры: {e}")
        db.rollback()

def update_stages(db: Session):
    """2. Обновление этапов"""
    print("\n--- [2/4] Обновление этапов... ---")
    valid_stages_map = {
        "blank": "Не выбрано",
        "disability_doc": "Справка по инвалидности",
        "mtz": "МТЗ",
        "ipra": "ИПРА",
        "wait_cert": "Ожидаем сертификат",
        "check_cert": "Пробитие сертификата",
        "wait_parts": "Ожидание комплектующих",
        "contract_sign": "Договор отправлен на подпись",
        "prosthetics": "Протезирование",
        "completed": "Выполнен",
        "cancelled": "Отменен",
        "need_cert": "Необходима подача сертификата",
        "call_prosthetics": "Вызов на протезирование"
    }

    try:
        for code, desc in valid_stages_map.items():
            stage = db.get(models.Stage, code)
            if not stage:
                db.add(models.Stage(stage_code=code, description=desc))
            else:
                stage.description = desc
        db.commit()

        # Чистка
        all_stages = db.query(models.Stage).all()
        for stage in all_stages:
            if stage.stage_code not in valid_stages_map:
                db.execute(
                    update(models.Client)
                    .where(models.Client.current_stage == stage.stage_code)
                    .values(current_stage="blank")
                )
                db.delete(stage)
        db.commit()
        print("✅ Этапы обновлены.")
    except Exception as e:
        print(f"❌ Ошибка этапов: {e}")
        db.rollback()

def migrate_price_to_string(db):
    """3. Миграция цены"""
    print("\n--- [3/4] Миграция цены... ---")
    try:
        # Проверяем тип колонки, чтобы не падать лишний раз
        # (упрощенно просто пробуем выполнить alter)
        sql = """
        ALTER TABLE "CLIENT" 
        ALTER COLUMN certificate_price TYPE VARCHAR(255) 
        USING certificate_price::varchar;
        """
        db.execute(text(sql))
        db.commit()
        print("✅ Успешно.")
    except Exception as e:
        print(f"ℹ️ Пропуск (уже конвертировано): {e}")
        db.rollback()

def migrate_data_to_refs(db: Session):
    """4. Миграция данных в справочники"""
    print("\n--- [4/4] Миграция данных... ---")
    
    clients = db.query(models.Client).all()
    unique_prothesis = set()
    unique_tsr = set()

    for c in clients:
        if c.prosthesis_type:
            parts = [pt.strip() for pt in c.prosthesis_type.replace(";", "\n").split("\n") if pt.strip()]
            for p in parts:
                if len(p) > 2: unique_prothesis.add(p)

        if c.tsr_code:
            parts = [ts.strip() for ts in c.tsr_code.replace(";", "\n").split("\n") if ts.strip()]
            for t in parts:
                if len(t) > 5: unique_tsr.add(t)

    # Вставка Протезов
    added_p = 0
    for name in unique_prothesis:
        exists = db.execute(text("SELECT 1 FROM \"REF_PROSTHESIS\" WHERE name = :n"), {"n": name}).first()
        if not exists:
            # ИСПОЛЬЗУЕМ prosthesis_id (как в models.py)
            db.execute(
                text("INSERT INTO \"REF_PROSTHESIS\" (prosthesis_id, name) VALUES (:id, :name)"),
                {"id": gen_uuid(), "name": name}
            )
            added_p += 1
    
    # Вставка ТСР
    added_t = 0
    for full_text in unique_tsr:
        exists = db.execute(text("SELECT 1 FROM \"REF_TSR\" WHERE full_tsr_code = :ft"), {"ft": full_text}).first()
        if not exists:
            # ИСПОЛЬЗУЕМ tsr_id (как в models.py)
            db.execute(
                text("INSERT INTO \"REF_TSR\" (tsr_id, full_tsr_code) VALUES (:id, :ft)"),
                {"id": gen_uuid(), "ft": full_text}
            )
            added_t += 1

    db.commit()
    print(f"✅ Протезов добавлено: {added_p}")
    print(f"✅ ТСР добавлено: {added_t}")

def main():
    db = SessionLocal()
    try:
        add_columns(db)
        update_stages(db)
        migrate_price_to_string(db)
        migrate_data_to_refs(db)
    finally:
        db.close()

if __name__ == "__main__":
    main()