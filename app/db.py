'''
Единое место для подключения к БД с фабрикой сессий.
Обеспечивает единый источник контроля пулов соединений, таймаутов, открытия/закрытия сессий в эндпоинтах.
'''
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

try:
    from app.config import settings
except ImportError:
    from config import settings

DATABASE_URL = settings.get_db_url()

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
