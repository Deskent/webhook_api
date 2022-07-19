import requests

from config import settings, logger


def send_message_to_admins(text: str) -> None:
    text = f'[Slarti][{settings.LOCATION}]: {text}'
    for admin in settings.ADMINS:
        send_message_to_user(telegram_id=admin, text=text)


def send_message_to_user(telegram_id: int, text: str) -> int:
    """
    The function of sending the message with the result of the script
    """
    url: str = f"https://api.telegram.org/bot{settings.TELEBOT_TOKEN}/sendMessage?chat_id={telegram_id}&text={text}"
    try:
        response = requests.get(url, timeout=5)

        logger.info(f"telegram id: {telegram_id}\n message: {text}")

        return response.status_code
    except Exception as err:
        logger.error(f"telegram id: {telegram_id}\n message: {text}\n requests error: {err}")

    return -1
