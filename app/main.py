# app/main.py
import warnings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

# Импорты БД
from app.db import engine, SessionLocal
from app import models

# 1. Создаем таблицы, если их нет
models.Base.metadata.create_all(bind=engine)

# 2. Функция наполнения справочников (Скрипт инициализации)
def init_db_data():
    db = SessionLocal()
    try:
        # --- СТАТУСЫ ---
        if db.query(models.Status).count() == 0:
            print("Initializing Statuses...")
            statuses = [
                models.Status(status_code="new", description="Новый"),
                models.Status(status_code="work", description="В работе"),
                models.Status(status_code="success", description="Успешно завершен"),
                models.Status(status_code="fail", description="Отказ"),
                models.Status(status_code="hold", description="Отложен"),
            ]
            db.add_all(statuses)
            db.commit()

        # --- ЭТАПЫ (Stages) ---
        if db.query(models.Stage).count() == 0:
            print("Initializing Stages...")
            stages = [
                models.Stage(stage_code="contact", description="Первичный контакт"),
                models.Stage(stage_code="meeting", description="Встреча/Переговоры"),
                models.Stage(stage_code="kp", description="Отправлено КП"),
                models.Stage(stage_code="contract", description="Договор"),
                models.Stage(stage_code="prepay", description="Предоплата"),
                models.Stage(stage_code="production", description="В производстве"),
                models.Stage(stage_code="shipping", description="Отгрузка"),
                models.Stage(stage_code="done", description="Закрытие актов"),
            ]
            db.add_all(stages)
            db.commit()
            
    except Exception as e:
        print(f"Error initializing data: {e}")
        db.rollback()
    finally:
        db.close()

# 3. Запускаем инициализацию
init_db_data()

# --- ДАЛЕЕ ВАШ ОБЫЧНЫЙ КОД ПРИЛОЖЕНИЯ ---

# Попытка импортировать роутеры
clients_router = None
agents_router = None
stages_router = None
status_router = None
passports_router = None
snils_router = None
phones_router = None
modules_router = None
auth_router = None
documents_router = None

try:
    from app.api import auth
    auth_router = auth.router
except Exception as e:
    warnings.warn(f"Auth router fail: {e!r}")

try:
    from app.api import clients
    clients_router = clients.router
except Exception as e:
    warnings.warn(f"Clients router fail: {e!r}")

try:
    from app.api import agents
    agents_router = agents.router
except Exception as e:
    warnings.warn(f"Agents router fail: {e!r}")

try:
    from app.api import stages
    stages_router = stages.router
except Exception as e:
    warnings.warn(f"Stages router fail: {e!r}")

try:
    from app.api import status as status_module
    status_router = status_module.router
except Exception as e:
    warnings.warn(f"Status router fail: {e!r}")

try:
    from app.api import passports
    passports_router = passports.router
except Exception as e:
    warnings.warn(f"Passports router fail: {e!r}")

try:
    from app.api import snils
    snils_router = snils.router
except Exception as e:
    warnings.warn(f"Snils router fail: {e!r}")

try:
    from app.api import phones
    phones_router = phones.router
except Exception as e:
    warnings.warn(f"Phones router fail: {e!r}")

try:
    from app.api import modules
    modules_router = modules.router
except Exception as e:
  warnings.warn(f"Modules router fail: {e!r}")

try:
    from app.api import documents
    documents_router = documents.router
except Exception as e:
    warnings.warn(f"Docs router fail: {e!r}")

# Documents api imports
try:
    from app.api import documents
    documents_router = documents.router
except Exception as e:
    warnings.warn(f"Docs router fail: {e!r}")


app = FastAPI(
    title="Documents API",
    version="0.1.0",
    description="API для хранения метаданных клиентов и ссылок на документы."
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутов
if auth_router: app.include_router(auth_router, prefix="/auth", tags=["auth"])
if clients_router: app.include_router(clients_router, prefix="/clients", tags=["clients"])
if agents_router: app.include_router(agents_router, prefix="/agents", tags=["agents"])
if stages_router: app.include_router(stages_router, prefix="/stages", tags=["stages"])
if status_router: app.include_router(status_router, prefix="/status", tags=["status"])
if passports_router: app.include_router(passports_router, prefix="/passports", tags=["documents"])
if snils_router: app.include_router(snils_router, prefix="/snils", tags=["documents"])
if phones_router: app.include_router(phones_router, prefix="/phones", tags=["clients"])
if modules_router: app.include_router(modules_router, prefix="/modules", tags=["modules"])
if documents_router: app.include_router(documents_router, prefix="/documents", tags=["documents"])
# Documents connection
if documents_router: app.include_router(documents_router, prefix="/documents", tags=["documents"])

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
def root():
    return HTMLResponse(content="<h1>Server is running</h1>", status_code=200)


# --- ВРЕМЕННЫЙ КОД ДЛЯ ОБНОВЛЕНИЯ ЭТАПОВ ---
from app import models
from sqlalchemy.orm import Session
from fastapi import Depends
from app.db import get_db
from sqlalchemy import update, delete

# @app.get("/cleanup_stages")
# def cleanup_stages(db: Session = Depends(get_db)):
#     # 1. Список этапов, которые ДОЛЖНЫ остаться
#     # (Все остальные будут удалены)
#     valid_stages_map = {
#         "blank": "Не выбрано",
#         "disability_doc": "Справка по инвалидности",
#         "mtz": "МТЗ",
#         "ipra": "ИПРА",
#         "wait_cert": "Ожидаем сертификат",
#         "check_cert": "Пробитие сертификата",
#         "wait_parts": "Ожидание комплектующих",
#         "contract_sign": "Договор отправлен на подпись",
#         "prosthetics": "Протезирование",
#         "completed": "Выполнен",
#         "cancelled": "Отменен",
#         "need_cert": "Необходима подача сертификата",
#         "call_prosthetics": "Вызов на протезирование"
#     }

#     # 2. Добавляем или обновляем
#     if not db.get(models.Stage, "blank"):
#         db.add(models.Stage(stage_code="blank", description="Не выбрано"))
#         db.commit()

#     # 3. Находим все этапы в базе
#     all_stages = db.query(models.Stage).all()
    
#     deleted_stages_count = 0
#     moved_clients_count = 0

#     for stage in all_stages:
#         # Если этапа нет в нашем "белом списке"
#         if stage.stage_code not in valid_stages_map:
#             # А. Переносим всех клиентов с этого этапа на "blank"
#             result = db.execute(
#                 update(models.Client)
#                 .where(models.Client.current_stage == stage.stage_code)
#                 .values(current_stage="blank")
#             )
#             moved_clients_count += result.rowcount
            
#             # Б. Удаляем сам этап
#             db.delete(stage)
#             deleted_stages_count += 1

#     db.commit()
    
#     return {
#         "status": "success",
#         "moved_clients": moved_clients_count,
#         "deleted_old_stages": deleted_stages_count,
#         "valid_stages_count": len(valid_stages_map)
#     }

@app.get("/add_module_columns")
def add_module_columns(db: Session = Depends(get_db)):
    from sqlalchemy import text
    try:
        db.execute(text("ALTER TABLE \"MODULES\" ADD COLUMN IF NOT EXISTS size VARCHAR(64)"))
        db.execute(text("ALTER TABLE \"MODULES\" ADD COLUMN IF NOT EXISTS stiffness VARCHAR(64)"))
        db.execute(text("ALTER TABLE \"MODULES\" ADD COLUMN IF NOT EXISTS side VARCHAR(64)"))
        db.commit()
        return {"status": "Columns added"}
    except Exception as e:
        return {"error": str(e)}