import logging
import requests


def _send_to_notifier(service: str, message: str):
    try:
        requests.post(
            "http://aerobot-error-notifier:60615/usageerror",
            json={
                "service": service,
                "number": None,
                "intent": None,
                "traceback": message,
                "additional_data": None,
            },
            timeout=3,
        )
    except Exception:
        pass


class _ErrorNotifierHandler(logging.Handler):
    def emit(self, record):
        _send_to_notifier(record.name, self.format(record))


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    error_handler = _ErrorNotifierHandler(level=logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)

    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger
