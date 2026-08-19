"""Cliente del SMN: cada host por el camino que le funciona.

## El mapa, medido el 18/ago desde el VPS de producción

    ws1.smn.gob.ar        listas de frames     ✅ 6/6 directo
    estaticos.smn.gob.ar  imágenes del radar   ✅ 6/6 directo (chrome + HTTP/3)
    www.smn.gob.ar        el token del radar   ❌ 0/12 directo  → browser
    ssl.smn.gob.ar        METAR/TAF/PRONAREA   ❌ 2/12 directo  → browser

Los dos primeros salen directo y ni se enteran de que existe un browser: son lo
pesado (~13 MB por video de radar) y pasarlos por el fetcher sería pagar RAM y
latencia a cambio de nada.

Los dos últimos están bloqueados **por la IP**, no por el fingerprint: el mismo
código, en el mismo momento, dio 12/12 desde una IP residencial y 0/12 desde el
VPS. Por eso ahí no alcanza con cambiar de perfil — va por `aerobot-smn-fetch`,
que tiene un browser de verdad resolviendo el challenge.

## La regla que no se negocia: nunca peor que hoy

Si el fetcher no está, o tarda, o contesta cualquier cosa, **se sale igual por
el camino directo**. Hoy ese camino funciona 2 de cada 12 veces contra `ssl`, y
2 de 12 es infinitamente mejor que un servicio nuevo convertido en requisito
nuevo. Un componente que agrega un modo de falla no puede ser obligatorio.
"""
import os

from curl_cffi.const import CurlHttpVersion

from aerocommons import http
from aerocommons.logger import get_logger

logger = get_logger(__name__)

FETCHER = os.getenv("SMN_FETCH_URL", "http://smn-fetch:60630")

#: Cuánto esperar al fetcher.
#:
#: 150 y no 40, que es lo que decía acá antes y era un error de dimensionado.
#: El peor camino real no es "arrancar el browser" (~25s): es que Cloudflare
#: sirva el challenge y el browser no lo resuelva a la primera, que **pasa** —
#: medido el 18/ago, dos arranques seguidos dieron uno 200 limpio y el otro 403
#: después de 40s. Ahí el fetcher cierra el browser, lo rearma con identidad
#: nueva y reintenta: 40s de challenge + ~25s de arranque + la navegación, o
#: sea 90-120s.
#:
#: Con el timeout en 40 el cliente se iba al camino directo **justo en los
#: casos donde el browser estaba por resolverlo** — el peor momento posible,
#: porque son exactamente las veces en que el directo tampoco va a poder.
TIMEOUT_FETCHER = int(os.getenv("SMN_FETCH_TIMEOUT", "150"))

#: Los que el browser tiene que resolver. El resto sale directo.
HOSTS_BLOQUEADOS = {"www.smn.gob.ar", "ssl.smn.gob.ar"}

#: Cada host del SMN está configurado distinto y son opuestos entre sí: medido,
#: `estaticos` anda con HTTP/3 y da 403 con HTTP/2, y `www` hace exactamente lo
#: contrario. No hay una combinación única que sirva para todo el SMN.
PROTOCOLO = {
    "estaticos.smn.gob.ar": CurlHttpVersion.V3,
    "ssl.smn.gob.ar": CurlHttpVersion.V3,
}


def host_de(url: str) -> str:
    return url.split("/")[2].split(":")[0] if "//" in url else ""


def necesita_browser(url: str) -> bool:
    return host_de(url) in HOSTS_BLOQUEADOS


class _RespuestaDelBrowser:
    """Lo que trajo el browser, con la forma de una respuesta de curl_cffi.

    Existe para que quien llama no tenga que preguntarse por dónde vino: el
    parser del METAR sigue haciendo `r.text` y no cambia una línea.
    """

    def __init__(self, status_code: int, texto: str):
        self.status_code = status_code
        self.text = texto
        self.content = texto.encode("utf-8", "replace")
        self.headers = {}
        self.via_browser = True

    def json(self):
        import json
        return json.loads(self.text)


def _directo(url, headers=None, **kwargs):
    kwargs.setdefault("http_version", PROTOCOLO.get(host_de(url)))
    if kwargs["http_version"] is None:
        kwargs.pop("http_version")
    return http.get(url, headers=headers, **kwargs)


def get(url: str, *, headers: dict | None = None, timeout: int = 30, **kwargs):
    """Trae una URL del SMN por el camino que corresponda a su host."""
    if not necesita_browser(url):
        return _directo(url, headers=headers, timeout=timeout, **kwargs)

    try:
        r = http.get(f"{FETCHER}/traer", params={"url": url}, timeout=TIMEOUT_FETCHER)
        if r.status_code == 200:
            d = r.json()
            return _RespuestaDelBrowser(d.get("status", 200), d.get("html", ""))
        logger.warning("el fetcher devolvió %s para %s — se sale directo",
                       r.status_code, url)
    except Exception:
        logger.warning("el fetcher no respondió para %s — se sale directo", url,
                       exc_info=True)

    return _directo(url, headers=headers, timeout=timeout, **kwargs)


def token(refrescar: bool = False) -> str | None:
    """El JWT del radar, que solo se puede sacar de `www.smn.gob.ar`.

    Devuelve None en vez de lanzar: quien lo llama ya tiene que saber qué hacer
    sin token (el flujo del radar se corta), y una excepción acá solo cambia
    dónde se rompe.
    """
    try:
        r = http.get(f"{FETCHER}/token", params={"refrescar": str(refrescar).lower()},
                     timeout=TIMEOUT_FETCHER)
        if r.status_code == 200:
            return r.json().get("token")
        logger.error("el fetcher no pudo dar token: %s %s", r.status_code, r.text[:200])
    except Exception:
        logger.error("el fetcher no respondió al pedir el token", exc_info=True)
    return None
