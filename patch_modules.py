import sys
import os
import uuid

sys.path.append(os.path.join(os.path.dirname(__file__)))
from sqlalchemy import text
from app.db import SessionLocal

def gen_uuid():
    return str(uuid.uuid4())

def run_patch():
    db = SessionLocal()
    try:
        print("1. Создание справочников...")
        db.execute(text('CREATE TABLE IF NOT EXISTS "REF_NameIndex" (name_index_id UUID PRIMARY KEY, name_index TEXT NOT NULL UNIQUE)'))
        db.execute(text('CREATE TABLE IF NOT EXISTS "REF_PROSTHETIST" (prosthetist_id UUID PRIMARY KEY, name TEXT NOT NULL UNIQUE)'))
        db.execute(text('CREATE TABLE IF NOT EXISTS "DOC_STATUS" (code VARCHAR(32) PRIMARY KEY, description TEXT NOT NULL)'))

        print("2. Добавление колонок (БЕЗ удаления старых)...")
        db.execute(text('ALTER TABLE "MODULES" ADD COLUMN IF NOT EXISTS module_name_index TEXT;'))
        db.execute(text('ALTER TABLE "CLIENT" ADD COLUMN IF NOT EXISTS prosthetist TEXT;'))
        db.execute(text('ALTER TABLE "CLIENT" ADD COLUMN IF NOT EXISTS contract_status VARCHAR(32);'))
        db.execute(text('ALTER TABLE "CLIENT" ADD COLUMN IF NOT EXISTS act_status VARCHAR(32);'))
        db.commit()

        print("3. Поиск и восстановление данных модулей...")
        
        # Сценарий А: если данные застряли в name_index (от первого патча)
        check_name_index = db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='MODULES' AND column_name='name_index'")).fetchone()
        if check_name_index:
            db.execute(text('UPDATE "MODULES" SET module_name_index = name_index WHERE module_name_index IS NULL AND name_index IS NOT NULL;'))
        
        # Сценарий Б: если данные всё ещё лежат в module_name и catalogue_index
        check_old_cols = db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='MODULES' AND column_name='module_name'")).fetchone()
        if check_old_cols:
            modules = db.execute(text('SELECT module_id, module_name, catalogue_index FROM "MODULES" WHERE module_name_index IS NULL')).fetchall()
            for m in modules:
                m_id = m[0]
                m_name = m[1].strip() if m[1] else ""
                c_idx = m[2].strip() if m[2] else ""
                combined = f"{m_name} {c_idx}".strip()
                if not combined:
                    combined = "Неизвестный модуль"
                db.execute(text('UPDATE "MODULES" SET module_name_index = :val WHERE module_id = :id'), {"val": combined, "id": m_id})

        db.commit()

        print("4. Заполнение справочника REF_NameIndex...")
        # Собираем все уникальные названия и кладем в справочник, чтобы они появились в выпадающем списке
        unique_names = db.execute(text('SELECT DISTINCT module_name_index FROM "MODULES" WHERE module_name_index IS NOT NULL')).fetchall()
        for row in unique_names:
            name_val = row[0].strip()
            exists = db.execute(text('SELECT 1 FROM "REF_NameIndex" WHERE name_index = :n'), {"n": name_val}).first()
            if not exists:
                db.execute(text('INSERT INTO "REF_NameIndex" (name_index_id, name_index) VALUES (:id, :n)'), {"id": gen_uuid(), "n": name_val})
        
        db.commit()
        print("✅ База данных полностью обновлена! Данные на месте.")

    except Exception as e:
        print(f"❌ Ошибка БД: {e}")
        db.rollback()
    finally:
        db.close()
import sys
import os
from sqlalchemy import text
from app.db import SessionLocal

sys.path.append(os.path.join(os.path.dirname(__file__)))

def run_patch_acc():
    db = SessionLocal()
    try:
        print("Добавление колонок зарплат в таблицу CLIENT...")
        # Добавляем колонки для 3 новых зарплат (тип FLOAT)
        db.execute(text('ALTER TABLE "CLIENT" ADD COLUMN IF NOT EXISTS prosthetist_salary FLOAT DEFAULT 0.0;'))
        db.execute(text('ALTER TABLE "CLIENT" ADD COLUMN IF NOT EXISTS agent_salary FLOAT DEFAULT 0.0;'))
        db.execute(text('ALTER TABLE "CLIENT" ADD COLUMN IF NOT EXISTS support_salary FLOAT DEFAULT 0.0;'))
        db.commit()
        print("✅ Колонки успешно добавлены в базу данных!")
    except Exception as e:
        print(f"❌ Ошибка БД: {e}")
        db.rollback()
    finally:
        db.close()

import sys
import os
from sqlalchemy import text
from app.db import SessionLocal

sys.path.append(os.path.join(os.path.dirname(__file__)))

def drop_foreign_keys():
    db = SessionLocal()
    try:
        print("1. Снимаем жесткие привязки (ForeignKey) с таблицы CLIENT...")
        
        # PostgreSQL генерирует названия ограничений по шаблону. Пытаемся удалить их:
        db.execute(text('ALTER TABLE "CLIENT" DROP CONSTRAINT IF EXISTS "CLIENT_prosthesis_type_fkey";'))
        db.execute(text('ALTER TABLE "CLIENT" DROP CONSTRAINT IF EXISTS "CLIENT_tsr_code_fkey";'))
        
        db.commit()
        print("✅ Ограничения успешно сняты! Теперь можно сохранять мульти-списки.")
    except Exception as e:
        print(f"❌ Ошибка БД: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    run_patch()
    run_patch_acc()
    drop_foreign_keys()