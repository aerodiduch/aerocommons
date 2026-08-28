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
            # Hay DOS status en juego y el que importa es el de adentro.
            # `r.status_code` dice si el fetcher contestó; `d["status"]` dice
            # qué le contestó el SMN al browser. Un fetcher sano que reporta
            # "el SMN me sirvió un challenge" viene como 200 con status 403
            # adentro, y devolver eso es entregar el HTML de Cloudflare como si
            # fuera el reporte: `WeatherParser` lo parsea, saca [] y le dice al
            # usuario "no encontré datos" — el mismo bug que `_es_challenge`
            # arregló del lado directo, reentrando por la puerta de atrás.
            #
            # Medido sobre las 115 rondas de la sonda (19-23/ago/2026): en 12
            # de ellas el browser trajo 403 y el camino directo funcionaba. Sin
            # este chequeo esas 12 se pierden teniendo el dato a mano, que es
            # exactamente lo que la regla de arriba promete que no pasa.
            estado_smn = d.get("status", 200)
            if estado_smn == 200:
                return _RespuestaDelBrowser(estado_smn, d.get("html", ""))
            logger.warning("el browser trajo %s del SMN para %s — se sale directo",
                           estado_smn, url)
        else:
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
