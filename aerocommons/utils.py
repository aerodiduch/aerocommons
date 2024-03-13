# Failsafe decorator
import traceback
from .api import send_error_log, send_text_message
from .request_parser import FacebookParser


def failsafe(func, from_facebook=False):
    """
    A decorator that wraps a function and handles exceptions by printing
    an error message and returning None.

    Args:
        func: The function to be wrapped.

    Returns:
        The wrapped function.

    Example:
        @failsafe
        def my_function():
            # code that could potentially raise an exception
    """

    # TODO: Estandarizar el payload para poder saber
    # siempre de donde sale el numero de telefono
    def wrapper(*args, **kwargs):
        if from_facebook:
            request = kwargs.get("request")
            data = FacebookParser(await request.json())
            phone_number = data.message_number

        try:
            return func(*args, **kwargs)
        except Exception:

            send_error_log(
                number=None,
                intent=func.__name__,
                traceback=traceback.format_exc(),
            )

            send_text_message(
                "data",
                phone_number,
                "🤖 Bzz! Temporalmente, *debido a la situación económica*, Aerobot *estará disponible solo para usuarios suscriptos*. \nSi queres *seguir usando aerobot como hasta ahora*, podes suscribrite por *$1500/mes* 👉🏻 https://aerobot.com.ar/apoyar.\n\nSi queres conocer más acerca de esta decisión 👉🏻 https://aerobot.com.ar/comunicado ",
            )

        finally:
            return "200 HTTPS OK"

    return wrapper
