'''
Единое место для подключения к БД с фабрикой сессий.
Обеспечивает единый источник контроля пулов соединений, таймаутов, открытия/закрытия сессий в эндпоинтах.
'''
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://daniel:801599@localhost:5432/documents_db"
)

# Engine управляет пулом соединений, координирует работу между бэкендом и СУБД
# pool - проверяет целостность соединения перед использованием
engine = create_engine(DATABASE_URL, pool_pre_ping = True, future = True)

# Фабрика сессий - временное рабочее пространство для выполнения операций:
# Отслеживает изменения, предосталвяет данные и группирует операции в транзакции внутри сессиии
# sessionmaker создает новые сессии с предустановленными настройками 
SessionLocal = sessionmaker(bind = engine, autoflush = False, autocommit = False, future = True)

# FastAPI dependency — гарантированно закроет сессию
def get_db():
    # Создание сессии в фабрике сессий
    db = SessionLocal()
    try:
    # Сессия направляется в обработчик запросов
        yield db
    finally:
        # Сессия всегда закрывается после работы
        db.close()
