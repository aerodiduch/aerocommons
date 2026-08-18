"""Cliente único para todo lo que Aerobot consulta del SMN.

Existe porque el SMN está detrás de Cloudflare y **el perfil de browser que
pasa el challenge cambia con el tiempo**: el 16/ago/2026 `firefox` pasaba 7 de
8 y todo Chromium daba 403; el 18/ago era exactamente al revés. Cada vez que se
da vuelta, el servicio queda roto hasta que alguien lo nota — el radar estuvo
12 días caído por eso.

Perseguir el perfil de moda es correr atrás del problema. Lo que no cambia es
que **Cloudflare emite una cookie `cf_clearance` a quien resuelve su challenge**,
y esa cookie:

  - vale para `Domain=smn.gob.ar`, o sea **todos** los subdominios (`www`,
    `ws1`, `estaticos`, `ssl`) -- un solo clearance cubre METAR, TAF, PRONAREA,
    AEROMET y radar;
  - trae `Expires` a un año (medido sobre un HAR real, 18/ago/2026).

`aerobot-smn-clearance` la consigue con un browser y la deja en Redis. Este
módulo la usa. Si no hay cookie, igual se intenta la request -- el clearance
**suma** tasa de éxito, no es un requisito nuevo para que el SMN funcione.

REGLAS QUE NO SE PUEDEN VIOLAR (cada una costó una medición):

1. **El User-Agent va con la cookie.** Cloudflare valida que quien la usa sea
   quien la obtuvo. Por eso se guardan juntos y se mandan juntos. Esta es la
   *única* excepción a la regla de no escribir el User-Agent a mano: acá no se
   inventa nada, se repite exactamente el del browser que sacó la cookie.
2. **El perfil de `impersonate` tiene que ser el mismo motor que el browser.**
   Chromium saca la cookie -> se impersona `chrome`. Un UA de Chrome sobre un
   TLS de Firefox es justo la contradicción que Cloudflare busca.
3. **HTTP/3.** Un browser real negocia h3 contra los cuatro hosts del SMN
   (verificado en el HAR). Pedir por HTTP/2 es una inconsistencia gratis.
"""
import os

from curl_cffi import requests as _curl
from curl_cffi.const import CurlHttpVersion

from .logger import get_logger

logger = get_logger(__name__)

CLAVE = "smn:clearance"

#: Chromium es lo que corre el servicio de clearance, así que el fingerprint
#: TLS tiene que ser de la misma familia. Si algún día se cambia el browser,
#: hay que cambiar esto en el mismo commit.
IMPERSONATE = os.getenv("SMN_IMPERSONATE", "chrome")

URL_CLEARANCE = os.getenv(
    "SMN_CLEARANCE_URL", "http://aerobot-smn-clearance:60630"
)


def _redis():
    try:
        import redis
        return redis.from_url(
            os.getenv("REDIS_URL", "redis://redis:6379/2"), decode_responses=True
        )
    except Exception:
        logger.warning("Sin Redis: se sale al SMN sin clearance", exc_info=True)
        return None


def _clearance() -> tuple[str | None, str | None]:
    r = _redis()
    if r is None:
        return None, None
    try:
        datos = r.hgetall(CLAVE)
    except Exception:
        logger.warning("No se pudo leer el clearance de Redis", exc_info=True)
        return None, None
    if not datos:
        return None, None
    return datos.get("cf_clearance"), datos.get("user_agent")


def _invalidar():
    """Se llama cuando el SMN rechaza una request que LLEVABA la cookie.

    Ese caso es distinto de un 403 cualquiera: significa que la cookie está
    quemada, no que falte. Borrarla hace que el próximo pedido dispare una
    renovación en vez de reintentar con algo que ya sabemos que no sirve.
    """
    r = _redis()
    if r is None:
        return
    try:
        if r.delete(CLAVE):
            logger.warning("cf_clearance quemada: se borró para forzar renovación")
    except Exception:
        logger.warning("No se pudo invalidar el clearance", exc_info=True)


def pedir_renovacion(timeout: int = 90) -> bool:
    """Le pide al servicio del browser una cookie nueva. Best-effort."""
    try:
        import requests  # interno entre contenedores: va con requests a propósito
        resp = requests.post(f"{URL_CLEARANCE}/renovar", timeout=timeout)
        ok = bool(resp.json().get("ok"))
        logger.info("Renovación de clearance pedida: ok=%s", ok)
        return ok
    except Exception:
        logger.warning("No se pudo pedir la renovación del clearance", exc_info=True)
        return False


def get(url: str, *, headers: dict | None = None, **kwargs):
    """GET al SMN con clearance si hay, y HTTP/3 como hace un browser real.

    Devuelve la respuesta tal cual -- decidir qué hacer con un 403 es del
    caller, que es quien sabe si tiene un fallback a mano.
    """
    cookie, ua = _clearance()
    cabeceras = dict(headers or {})

    if cookie:
        previa = cabeceras.get("cookie") or cabeceras.get("Cookie") or ""
        cabeceras["cookie"] = f"{previa}; cf_clearance={cookie}".lstrip("; ")
        if ua:
            # Ver regla 1 del docstring: acá el UA no se inventa, se repite.
            cabeceras["user-agent"] = ua

    kwargs.setdefault("http_version", CurlHttpVersion.V3)
    respuesta = _curl.get(url, impersonate=IMPERSONATE, headers=cabeceras, **kwargs)

    if respuesta.status_code in (403, 503) and cookie:
        _invalidar()

    return respuesta
