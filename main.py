from fastapi import FastAPI

from routers import api_router
from config import logger, settings
from services.utils import send_message_to_admins
from _resources import __version__, __appname__, __build__


@logger.catch
def get_application() -> FastAPI:
    """Start func"""

    send_message_to_admins(f"{__appname__.title()} started."
                           f"\nBuild:[{__build__}]"
                           f"\nVersion:[{__version__}]"
                           f"\nLocation: [{settings.LOCATION}]"
    )
    application = FastAPI()
    application.include_router(api_router)

    return application


app = get_application()
