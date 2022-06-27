from fastapi import FastAPI

from routers import api_router
from database import db_connect
from config import logger
from services.utils import send_message_to_admins
from _resources import __version__, __appname__, __build__


@logger.catch
def get_application() -> FastAPI:
    """Start func"""

    send_message_to_admins(f"{__appname__.title()} started."
                           f"\nBuild:[{__build__}]"
                           f"\nVersion:[{__version__}]"
    )
    application = FastAPI()
    db_connect(application)
    application.include_router(api_router)

    return application


app = get_application()
