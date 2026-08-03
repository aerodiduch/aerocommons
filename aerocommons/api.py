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


def get_template(key: str, service: str = None, fallback: str = None) -> str:
    """Resuelve un mensaje del catálogo centralizado (Mongo, vía
    aerobot-default-messages) por su `key`. `fallback` es obligatorio en la
    práctica -- es lo que se devuelve si default-messages no responde (Mongo
    caído, timeout, lo que sea), para que el envío de mensajes del bot nunca
    dependa de que este sistema esté sano. Mismo criterio que ya usa
    default-messages internamente (fallback a su dict estático si Mongo/
    db-connector no responden).

    Si default-messages no respondió bien, se reporta al Error Tracker --
    a diferencia del resto de las funciones de este módulo, acá SÍ importa
    que quede visible: es el único lugar donde "todo sigue funcionando"
    (el fallback) puede estar escondiendo que el sistema de templates está
    degradado, sin que nadie se entere.
    """
    try:
        resp = requests.post(
            "http://default-messages:60610/get_message",
            json={"template": key, "service": service},
            timeout=3,
        )
        value = resp.json().get("response")
        if value:
            return value
    except Exception:
        pass
    send_error_log(
        intent="get_template_fallback",
        additional_data=f"key={key} service={service}",
        service=service,
    )
    return fallback
