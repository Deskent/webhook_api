from pydantic import BaseSettings

from myloguru.my_loguru import get_logger


class Settings(BaseSettings):
    SERVER_HOST: str = '127.0.0.1'
    SERVER_PORT: int = 8000
    DEBUG: bool = False
    ADMINS: list
    TELEBOT_TOKEN: str
    STAGE: str
    STAGES: dict
    CLIENTS: list
    APPLICATIONS: list
    GITHUB_SECRET: str
    LOCATION: str


class Database(BaseSettings):
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str

    def get_db_name(self):
        return f"postgres://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"


db = Database(
    _env_file='.env',
    _env_file_encoding='utf-8'
)

settings = Settings(
    _env_file='.env',
    _env_file_encoding='utf-8'
)

level = 1 if settings.DEBUG else 20
logger = get_logger(level=level)

DATABASE_CONFIG = {
    "connections": {"default": db.get_db_name()},
    "apps": {
        "models": {
            "models": [
                "aerich.models",
                "models.models"
            ],
            "default_connection": "default",
        },
    },
}
