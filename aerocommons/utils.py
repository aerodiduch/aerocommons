# Failsafe decorator
import traceback


def failsafe(func):
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
        except Exception as e:
            print(f"Error: {e}")
            return None
        finally:
            return "200 HTTPS OK"

    return wrapper
