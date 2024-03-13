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

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            if from_facebook:
                request = kwargs.get("request")
                data = FacebookParser(await request.json())

            send_error_log(
                number=None,
                intent=func.__name__,
                traceback=traceback.format_exc(),
            )

            # TODO: Estandarizar el payload para poder saber
            # siempre de donde sale el numero de telefono

        finally:
            return "200 HTTPS OK"

    return wrapper
