# Conclave_Base

HTTP Request (JSON)
        ↓
FastAPI (парсит JSON)
        ↓
Валидация через schemas.ModuleCreate
        ↓
Передача в api_create_module(payload, db)
        ↓
CRUD слой (create_module)
        ↓
SQLAlchemy (работа с БД)
        ↓
Возврат models.Module (из БД)
        ↓
Сериализация через response_model=ModuleRead
        ↓
HTTP Response (JSON)