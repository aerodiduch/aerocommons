# Failsafe decorator
import traceback
from .api import send_error_log, send_text_message
from .request_parser import FacebookParser


async def failsafe(func, from_facebook=False):
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
    async def wrapper(*args, **kwargs):
        req = (await kwargs.get("request")).json()
        phone_number = req.get("phone_number")

        if from_facebook:
            request = kwargs.get("request")
            data = FacebookParser(await request.json())
            phone_number = data

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
                "🤖 Bzz! Hubo un problema procesando tu solicitud, ya estoy investigando que pasó 🐒 🔧",
            )

        finally:
            return "200 HTTPS OK"

    return wrapper
