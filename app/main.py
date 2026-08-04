# app/main.py
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.db import engine, SessionLocal
from app import models

try:
    from app.config import settings
except ImportError:
    from config import settings

from app.api import (
    accounting,
    agents,
    audit,
    auth,
    clients,
    documents,
    modules,
    passports,
    phones,
    references,
    snils,
    stages,
    status as status_module,
    accounting_report,
)

# Для разработки оставляем create_all, но для production/миграции на Vue лучше перейти на Alembic.
models.Base.metadata.create_all(bind=engine)


STATUS_DEFAULTS: dict[str, str] = {
    "new": "Новый",
    "work": "В работе",
    "fail": "Отказ",
    "hold": "Отложен",
    "success": "Успешно завершен",
}

STAGE_DEFAULTS: dict[str, str] = {
    "contact": "Первичный контакт",
    "meeting": "Встреча/Переговоры",
    "contract": "Договор",
    "prepay": "Оплата",
    "production": "Протезирование",
    "done": "Закрытие актов",
    "shipping": "Выполнено",
}


def init_db_data() -> None:
    """Создать или синхронизировать системные справочники по стабильным кодам.

    В отличие от прежней реализации, обновление выполняется и тогда, когда
    таблицы уже содержат записи. Поэтому изменение подписи в словарях выше
    применяется после пересборки и перезапуска приложения.
    """
    db = SessionLocal()
    try:
        for status_code, description in STATUS_DEFAULTS.items():
            db.merge(
                models.Status(
                    status_code=status_code,
                    description=description,
                )
            )

        for stage_code, description in STAGE_DEFAULTS.items():
            db.merge(
                models.Stage(
                    stage_code=stage_code,
                    description=description,
                )
            )

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


init_db_data()

app = FastAPI(
    title="Documents API",
    version="0.2.0",
    description="API для хранения метаданных клиентов, документов, склада, бухгалтерии и аудита.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(clients.router, prefix="/clients", tags=["clients"])
app.include_router(agents.router, prefix="/agents", tags=["agents"])
app.include_router(stages.router, prefix="/stages", tags=["stages"])
app.include_router(status_module.router, prefix="/status", tags=["status"])
app.include_router(passports.router, prefix="/passports", tags=["documents"])
app.include_router(snils.router, prefix="/snils", tags=["documents"])
app.include_router(phones.router, prefix="/phones", tags=["clients"])
app.include_router(modules.router, prefix="/components", tags=["components"])
# Скрытый совместимый адрес для старых клиентских сборок. В актуальном UI и
# OpenAPI бывшие "модули" представлены только как комплектующие.
app.include_router(modules.router, prefix="/modules", include_in_schema=False)
app.include_router(documents.router, prefix="/documents", tags=["documents"])
app.include_router(references.router, prefix="/references", tags=["references"])
app.include_router(accounting.router, prefix="/accounting", tags=["accounting"])
app.include_router(audit.router, prefix="/audit", tags=["audit"])
app.include_router(accounting_report.router)


@app.get("/health")
def health():
    return {"status": "ok"}



FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend-vue" / "dist"
FRONTEND_INDEX = FRONTEND_DIST / "index.html"
FRONTEND_ASSETS = FRONTEND_DIST / "assets"

if FRONTEND_ASSETS.exists():
    app.mount("/app/assets", StaticFiles(directory=str(FRONTEND_ASSETS)), name="frontend-assets")
    # Совместимость со старыми сборками Vite, где assets могли быть прописаны от корня /assets/.
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_ASSETS)), name="frontend-assets-root")


@app.get("/", response_class=HTMLResponse)
def root():
    if FRONTEND_INDEX.exists():
        return RedirectResponse(url="/app/")

    return HTMLResponse(content="<h1>Server is running</h1>", status_code=200)


@app.get("/app", include_in_schema=False)
@app.get("/app/", include_in_schema=False)
@app.get("/app/{full_path:path}", include_in_schema=False)
def frontend_app(full_path: str = ""):
    if FRONTEND_INDEX.exists():
        return FileResponse(FRONTEND_INDEX)

    return HTMLResponse(content="<h1>Frontend build not found</h1>", status_code=404)
