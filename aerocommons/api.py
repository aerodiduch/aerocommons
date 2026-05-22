import requests


def send_text_message(data, number, msg, ads=None, intent="get_notam"):
    """Sends a WhatsApp message to a user via the sendmsg service.

    Args:
        data (str): Raw data string.
        number (str): Phone number in string form.
        msg (str): Message body to send.
        ads (list, optional): Aerodrome list. Defaults to None.
        intent (str, optional): Intent identifier. Defaults to "get_notam".
    """
    return requests.post(
        "http://sendmsg:60611/sendmsg",
        json={
            "data": data,
            "number": number,
            "intent": intent,
            "msg": msg,
            "aerodromes": ads,
        },
        timeout=5,
    )


def send_error_log(number=None, intent=None, traceback=None, additional_data=None, service=None):
    try:
        requests.post(
            "http://aerobot-error-notifier:60615/usageerror",
            json={
                "service": service,
                "number": number,
                "intent": intent,
                "traceback": traceback,
                "additional_data": additional_data,
            },
            timeout=20,
        )
    except Exception:
        pass


def send_buttons_message(
    target_number: str, text_body: str, btn_ids: list, btn_texts: list
):
    try:
        requests.post(
            "http://sendmsg:60611/sendbtnmessage",
            json={
                "target_number": target_number,
                "text_body": text_body,
                "btn_ids": btn_ids,
                "btn_texts": btn_texts,
            },
        )
    except Exception:
        pass


def is_user_premium(phone_number: str = None):
    """Checks if user is premium or not. Returns a dict containing relevant user data."""
    response = requests.post(
        "http://db-connector:60610/ops",
        json={"op": "premium_check", "parameter": phone_number},
    )
    return response.json()
