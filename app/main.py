# app/main.py
"""
Точка входа FastAPI для проекта Documents API.
Содержит подключение роутеров, CORS, health-check и красивую стартовую страницу.
"""

import warnings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

# Попытка импортировать роутеры — если их ещё нет, приложение всё равно запустится.
clients_router = None
agents_router = None
stages_router = None
status_router = None
passports_router = None
snils_router = None
phones_router = None
modules_router = None

try:
    from app.api import auth
    auth_router = auth.router
except Exception as e:
    warnings.warn(f"Не удалось импортировать auth router: {e!r}")

try:
    from app.api import clients
    clients_router = clients.router
except Exception as e:
    warnings.warn(f"Не удалось импортировать clients router: {e!r}")

try:
    from app.api import agents
    agents_router = agents.router
except Exception as e:
    warnings.warn(f"Не удалось импортировать agents router: {e!r}")

# stages (справочник этапов)
try:
    from app.api import stages
    stages_router = stages.router
except Exception as e:
    warnings.warn(f"Не удалось импортировать stages router: {e!r}")

# status (справочник статусов) — импорт с alias, чтобы не путать с модулем `status`
try:
    from app.api import status as status_module
    status_router = status_module.router
except Exception as e:
    warnings.warn(f"Не удалось импортировать status router: {e!r}")

# Новые роутеры для документов
try:
    from app.api import passports
    passports_router = passports.router
except Exception as e:
    warnings.warn(f"Не удалось импортировать passports router: {e!r}")

try:
    from app.api import snils
    snils_router = snils.router
except Exception as e:
    warnings.warn(f"Не удалось импортировать snils router: {e!r}")

try:
    from app.api import phones
    phones_router = phones.router
except Exception as e:
    warnings.warn(f"Не удалось импортировать phones router: {e!r}")

try:
    from app.api import modules
    modules_router = modules.router
except Exception as e:
  warnings.warn(f"Не удалось импортировать modules router: {e!r}")


app = FastAPI(
    title="Documents API",
    version="0.1.0",
    description="API для хранения метаданных клиентов и ссылок на документы (S3/MinIO)."
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # в проде ограничить
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутов
if auth_router is not None:
    app.include_router(auth_router, prefix="/auth", tags=["auth"])
    
if clients_router is not None:
    app.include_router(clients_router, prefix = "/clients", tags = ["clients"])

if agents_router is not None:
    app.include_router(agents_router, prefix = "/agents", tags = ["agents"])

if stages_router is not None:
    app.include_router(stages_router, prefix = "/stages", tags = ["stages"])

if status_router is not None:
    app.include_router(status_router, prefix = "/status", tags = ["status"])

if passports_router is not None:
    app.include_router(passports_router, prefix = "/passports", tags = ["documents"])

if snils_router is not None:
    app.include_router(snils_router, prefix = "/snils", tags = ["documents"])
    
if phones_router is not None:
    app.include_router(phones_router, prefix = "/phones", tags = ["clients"])

if modules_router is not None:
  app.include_router(modules_router, prefix="/modules", tags=["modules"])

# Простой health-check
@app.get("/health")
def health():
    return {"status": "ok"}

