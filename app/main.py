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

        # --- ЭТАПЫ ---
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

