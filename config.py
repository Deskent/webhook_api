from pathlib import Path

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
    CLIENTS: list = []
    APPLICATIONS: list = []
    GITHUB_SECRET: str
    LOCATION: str
    UPDATE: list = []

BASE_DIR = Path(__file__).parent
settings = Settings(
    _env_file='.env',
    _env_file_encoding='utf-8'
)

level = 1 if settings.DEBUG else 20
logger = get_logger(level=level)
