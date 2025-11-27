import os
from pydantic_settings import BaseSettings, SettingsConfigDict # модели настроек и конфигуратор поведения загрузки настроек

class Settings(BaseSettings): # автоматически загружает переменные из .env
    DB_USER : str
    DB_PASSWORD : str
    DB_HOST : str = "localhost"
    DB_PORT : int = 5432 
    DB_NAME : str

    # app
    DEBUG : bool # флаг отладки с автоматическим преобразованием
    SECRET_KEY: str
    LOG_LEVEL: str = "INFO" # уровень логирования с значением по умолчанию

    # Docker
    COMPOSE_PROJECT_NAME: str = "db_app" # объявление переменной Docker со значением по умолчанию.

    model_config = SettingsConfigDict(
        env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
        env_file_encoding = 'UTF-8'
    # env_file=os.path.join(...) - путь к .env файлу:
    # __file__ - путь к текущему файлу (config.py)
    #os.path.abspath(__file__) - абсолютный путь к config.py
    #os.path.dirname(...) - директория где лежит config.py
    #os.path.join(..., ".env") - полный путь к .env файлу в той же папке
    )

    def get_db_url(self): # генерация url для асинхронного подключения к базе
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

settings = Settings() # экземпляр настроек, который: 1) читает .env файл 2) проверяет обязательные поля 
# 3) Преобразует типы 4) Применяет значения по умолчанию для незаданных полей

print("db url =>", settings.get_db_url())
print("DB HOST =>", settings.DB_HOST)