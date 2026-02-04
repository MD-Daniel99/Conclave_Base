import sys
import os

# Добавляем текущую директорию в путь, чтобы Python видел папку app
sys.path.append(os.path.join(os.path.dirname(__file__)))

from sqlalchemy import text, update, delete
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app import models

def add_columns(db: Session):
    """Добавление новых колонок в таблицы"""
    print("\n--- [1/2] Проверка и добавление колонок... ---")
    try:
        # MODULES
        db.execute(text("ALTER TABLE \"MODULES\" ADD COLUMN IF NOT EXISTS size VARCHAR(64)"))
        db.execute(text("ALTER TABLE \"MODULES\" ADD COLUMN IF NOT EXISTS stiffness VARCHAR(64)"))
        db.execute(text("ALTER TABLE \"MODULES\" ADD COLUMN IF NOT EXISTS side VARCHAR(64)"))
        db.execute(text("ALTER TABLE \"MODULES\" ADD COLUMN IF NOT EXISTS prosthetist_keep VARCHAR(64)"))
        # CLIENT
        db.execute(text("ALTER TABLE \"CLIENT\" ADD COLUMN IF NOT EXISTS ipra_code VARCHAR(64)"))
        db.execute(text("ALTER TABLE \"CLIENT\" ADD COLUMN IF NOT EXISTS place_of_residence VARCHAR(255)"))
        db.execute(text("ALTER TABLE \"MODULES\" DROP COLUMN IF EXISTS tsr_code"))
        db.execute(text("ALTER TABLE \"CLIENT\" ADD COLUMN IF NOT EXISTS tsr_code TEXT"))
        
        db.commit()
        print("✅ Колонки успешно добавлены (или уже существовали).")
    except Exception as e:
        print(f"❌ Ошибка при добавлении колонок: {e}")
        db.rollback()

def update_stages(db: Session):
    """Обновление списка этапов и миграция клиентов"""
    print("\n--- [2/2] Обновление этапов (Stages)... ---")
    
    # Полный список актуальных этапов
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
        # 1. Создаем или обновляем ВСЕ правильные этапы
        print("Актуализация списка этапов...")
        for code, desc in valid_stages_map.items():
            stage = db.get(models.Stage, code)
            if not stage:
                db.add(models.Stage(stage_code=code, description=desc))
            else:
                stage.description = desc
        
        # Фиксируем создание новых этапов перед миграцией
        db.commit()

        # 2. Находим старые этапы (которых нет в нашем списке)
        all_stages = db.query(models.Stage).all()
        deleted_stages_count = 0
        moved_clients_count = 0

        for stage in all_stages:
            if stage.stage_code not in valid_stages_map:
                print(f"  -> Найден устаревший этап: '{stage.stage_code}'.")
                
                # А. Переносим клиентов на 'blank'
                result = db.execute(
                    update(models.Client)
                    .where(models.Client.current_stage == stage.stage_code)
                    .values(current_stage="blank")
                )
                cnt = result.rowcount
                moved_clients_count += cnt
                if cnt > 0:
                    print(f"     Перенесено клиентов: {cnt}")
                
                # Б. Удаляем сам этап
                db.delete(stage)
                deleted_stages_count += 1

        db.commit()
        
        print(f"✅ Готово!")
        print(f"   - Перенесено клиентов на 'Не выбрано': {moved_clients_count}")
        print(f"   - Удалено старых этапов: {deleted_stages_count}")
        print(f"   - Всего актуальных этапов: {len(valid_stages_map)}")

    except Exception as e:
        print(f"❌ Ошибка при обновлении этапов: {e}")
        db.rollback()

def migrate_price_to_string(db):
    print("\n--- Миграция certificate_price в String... ---")
    try:
        # Команда ALTER TABLE с указанием USING для конвертации данных
        # ::varchar превращает число 1000.0 в строку "1000.0"
        sql = """
        ALTER TABLE "CLIENT" 
        ALTER COLUMN certificate_price TYPE VARCHAR(255) 
        USING certificate_price::varchar;
        """
        
        db.execute(text(sql))
        db.commit()
        print("✅ Успешно конвертировано!")
    except Exception as e:
        print(f"⚠️ Ошибка (возможно, уже применено): {e}")
        db.rollback()

def main():
    # Создаем сессию вручную
    db = SessionLocal()
    try:
        add_columns(db)
        update_stages(db)
        migrate_price_to_string(db)
    finally:
        db.close()

if __name__ == "__main__":
    main()
