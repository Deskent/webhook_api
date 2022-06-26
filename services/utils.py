import requests

from config import settings, logger


def send_message_to_admins(text: str) -> None:
    for admin in settings.ADMINS:
        url: str = f"https://api.telegram.org/bot{settings.TELEBOT_TOKEN}/sendMessage?chat_id={admin}&text={text}"
        try:
            requests.get(url, timeout=5)
        except Exception as err:
            logger.error(f"requests error: {err}")


def send_message_to_user(telegram_id: int, message: str) -> None:
    """
    The function of sending the message with the result of the script
    """
    url: str = f"https://api.telegram.org/bot{settings.TELEBOT_TOKEN}/sendMessage?chat_id={telegram_id}&text={message}"
    try:
        requests.get(url, timeout=5)
        logger.info(f"telegram id: {telegram_id}\n message: {message}")
    except Exception as err:
        logger.error(f"telegram id: {telegram_id}\n message: {message}\n requests error: {err}")
