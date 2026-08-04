"""Instrumentación de latencia para los servicios que NO son aerobot-weather.

Contexto (vault/proyectos/aerobot/roadmap-fixes.md, auditoría de KPIs del
04/ago/2026, pendiente #5): hasta ahora **solo `aerobot-weather` estaba
instrumentado**. La pregunta "¿el bot está lento?" únicamente se podía responder
para el camino de clima; notam, madhel, tiempo, radares y notifications eran una
caja negra.

`aerobot-weather` tiene su propio `metrics.py` (318 líneas, con `contextvars`)
porque necesita seguir fetches externos que corren en un `ThreadPoolExecutor`.
**Este módulo NO reemplaza aquel** ni intenta igualarlo: los demás servicios no
tienen paralelismo interno, así que alcanza con medir la request end-to-end. Es
deliberadamente más chico y más tonto.

Regla dura, heredada de `weather/metrics.py`: **nunca puede romper ni enlentecer
una respuesta real a un usuario.** Todo lo que puede fallar se traga en
silencio; el hot path no toca la red (escribe en un buffer en memoria y un hilo
de background hace el flush).

Uso, dos líneas en el servicio:

    from aerocommons.service_metrics import instrumentar
    instrumentar(app, "notam")
"""
import logging
import os
import threading
import time
from collections import deque

import requests

logger = logging.getLogger(__name__)

DB_CONNECTOR_URL = os.getenv("DB_CONNECTOR_URL", "http://db-connector:60610/ops")
FLUSH_INTERVAL_SECONDS = 10
MAX_BUFFER = 1000

# Rutas que no aportan nada al análisis y solo generan ruido y escrituras.
RUTAS_IGNORADAS = {"/docs", "/openapi.json", "/redoc", "/favicon.ico", "/health"}

_buffer = deque(maxlen=MAX_BUFFER)  # acotado: si el flush falla, se pierden los
_buffer_lock = threading.Lock()     # más viejos en vez de comerse la memoria
_flusher_iniciado = False
_flusher_lock = threading.Lock()


def _flush():
    with _buffer_lock:
        if not _buffer:
            return
        lote = list(_buffer)
        _buffer.clear()
    try:
        # Se reusa el op `insert_metrics` que ya existía para aerobot-weather,
        # con su whitelist de colecciones -- el contrato ya estaba pensado para
        # admitir métricas nuevas sin cambiar de forma.
        requests.post(
            DB_CONNECTOR_URL,
            json={"op": "insert_metrics",
                  "parameter": {"collection": "service_latency", "docs": lote}},
            timeout=5,
        )
    except Exception:
        # A propósito NO se reencolan: si db-connector está caído, reintentar
        # indefinidamente haría crecer el lote hasta que el flush tarde más que
        # el intervalo. Perder métricas es aceptable; acumular presión no.
        logger.warning("No se pudieron enviar %s métricas de servicio", len(lote))


def _loop_flush():
    while True:
        time.sleep(FLUSH_INTERVAL_SECONDS)
        try:
            _flush()
        except Exception:
            logger.warning("Fallo el ciclo de flush de métricas", exc_info=True)


def _asegurar_flusher():
    global _flusher_iniciado
    with _flusher_lock:
        if _flusher_iniciado:
            return
        hilo = threading.Thread(target=_loop_flush, daemon=True, name="service-metrics-flush")
        hilo.start()
        _flusher_iniciado = True


def registrar(servicio: str, ruta: str, duration_ms: float, status: str = "ok"):
    """Encola una medición. No hace I/O: solo escribe en el buffer en memoria."""
    try:
        _buffer.append({
            "service": servicio,
            "path": ruta,
            "duration_ms": round(duration_ms, 1),
            "status": status,
            "ts": time.time(),
        })
    except Exception:
        pass


def instrumentar(app, servicio: str):
    """Agrega a una app de FastAPI un middleware que mide cada request.

    `servicio` es el nombre que va a aparecer en el dashboard ("notam",
    "madhel"...). El middleware mide el tiempo total de la request, incluyendo
    lo que el servicio haya esperado de terceros -- que es justamente lo que
    interesa: cuánto esperó el usuario.
    """
    _asegurar_flusher()

    @app.middleware("http")
    async def _medir(request, call_next):
        ruta = request.url.path
        if ruta in RUTAS_IGNORADAS:
            return await call_next(request)

        inicio = time.perf_counter()
        estado = "ok"
        try:
            respuesta = await call_next(request)
            if respuesta.status_code >= 500:
                estado = "error"
            return respuesta
        except Exception:
            estado = "error"
            raise
        finally:
            # En `finally` para que una excepción del handler igual quede
            # medida -- si no, los caminos que fallan (los que más importan)
            # serían justo los que no se registran.
            registrar(servicio, ruta, (time.perf_counter() - inicio) * 1000, estado)

    return app


def instrumentar_flask(app, servicio: str):
    """Equivalente de `instrumentar` para Flask (lo usa `aerobot-radares`,
    que corre sobre gunicorn/Flask y no FastAPI)."""
    from flask import g, request

    _asegurar_flusher()

    @app.before_request
    def _inicio():
        g._metrica_inicio = time.perf_counter()

    @app.after_request
    def _fin(response):
        inicio = getattr(g, "_metrica_inicio", None)
        if inicio is not None and request.path not in RUTAS_IGNORADAS:
            registrar(
                servicio, request.path, (time.perf_counter() - inicio) * 1000,
                "error" if response.status_code >= 500 else "ok",
            )
        return response

    return app
