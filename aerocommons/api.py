from .utils import failsafe
import requests


def send_text_message(data, number, msg, ads=None):
    """Sends a message to the user

    Args:
        data (_type_): _description_
        number (str): Phone number in string form
        msg (str): String containing the message.
        ads (_type_, optional): _description_. Defaults to None.
    """
    requests.post(
        "http://sendmsg:60611/sendmsg",
        json={
            "data": data,
            "number": number,
            "intent": "get_notam",
            "msg": msg,
            "aerodromes": ads,
        },
        timeout=2,
    )


def send_error_log(number=None, intent=None, traceback=None):
    requests.post(
        "http://aerobot-error-notifier:60615/usageerror",
        json={"number": number, "intent": intent, "traceback": traceback},
        timeout=2,
    )


def is_user_premium(phone_number: str = None):
    """Checks if user is premium or not. Returns a dict
    containing relevant user data."""
    response = requests.post(
        "http://db-connector:60610/ops",
        json={"op": "premium_check", "parameter": phone_number},
    )
    return response.json()


def code_conversion():
    pass


def send_button_message():
    pass
