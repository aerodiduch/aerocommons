"""Cliente HTTP para todo lo que sale de Aerobot hacia afuera.

REGLA DURA (15/ago/2026, pedido explícito de Federico): **toda request a un
servicio EXTERNO sale por acá**, nunca con `requests` pelado.

El motivo es que `requests` se delata solo de dos formas, y las dos las mira
cualquier WAF moderno:

1. Manda `User-Agent: python-requests/2.x` -- un cartel que dice "soy un bot".
2. Su handshake TLS tiene un fingerprint (JA3) de Python/OpenSSL que no se
   parece al de ningún browser real, aunque le pises el User-Agent a mano.

`curl_cffi` con `impersonate="chrome"` resuelve las dos: copia el ClientHello
de un Chrome real, con su orden de cipher suites, extensiones y ALPN. Ya está
medido en este proyecto contra el SMN (aerobot-weather/WeatherParser.py):
HTTP/2 ~70-73% de éxito, HTTP/3 100%.

**Qué NO pasa por acá**: las llamadas internas entre contenedores
(`http://codes:60610`, `http://sendmsg:60611`, `http://db-connector:60610`).
Van por la red interna de Docker, no hay WAF que las mire, y cambiarlas sería
meter una dependencia nueva en un camino que ya funciona sin ganar nada.

**Qué NO arregla**: si el bloqueo es por IP (los paquetes se descartan antes
del TLS), ningún fingerprint ayuda -- no hay handshake que imitar. Eso se
resuelve cambiando de IP de salida, no de cliente HTTP. Ver la investigación
del bloqueo de ANAC en el vault.
"""
from curl_cffi import requests as _curl
from curl_cffi.const import CurlHttpVersion

# Se reexportan para que los callers puedan capturar excepciones sin tener que
# importar curl_cffi ellos mismos (y sin quedar atados a esta implementación).
# La jerarquía es la misma de `requests`: Timeout y ConnectionError heredan de
# RequestException.
exceptions = _curl.exceptions
Timeout = _curl.exceptions.Timeout
ConnectionError = _curl.exceptions.ConnectionError
RequestException = _curl.exceptions.RequestException
HTTPError = _curl.exceptions.HTTPError

# Chrome es el que está medido contra SMN y ANAC. Cambiarlo es un experimento,
# no un detalle: cada perfil tiene un fingerprint distinto.
DEFAULT_IMPERSONATE = "chrome"


def get(url: str, *, impersonate: str = DEFAULT_IMPERSONATE, http3: bool = False, **kwargs):
    """GET a un servicio externo, con fingerprint de browser real.

    `http3=True` fuerza HTTP/3 (QUIC). Solo tiene sentido donde está medido que
    el destino lo prefiere -- hoy el SMN. Contra el resto se deja en False, que
    negocia HTTP/2 como lo haría Chrome.
    """
    if http3:
        kwargs["http_version"] = CurlHttpVersion.V3
    return _curl.get(url, impersonate=impersonate, **kwargs)


def post(url: str, *, impersonate: str = DEFAULT_IMPERSONATE, http3: bool = False, **kwargs):
    """POST a un servicio externo, con fingerprint de browser real.

    OJO: a diferencia de `requests.post(url, data_dict)`, acá el cuerpo va
    SIEMPRE por keyword (`data=...` o `json=...`) -- curl_cffi no acepta el
    segundo argumento posicional. Migrar sin ajustar eso es un TypeError en
    runtime.
    """
    if http3:
        kwargs["http_version"] = CurlHttpVersion.V3
    return _curl.post(url, impersonate=impersonate, **kwargs)


def put(url: str, *, impersonate: str = DEFAULT_IMPERSONATE, http3: bool = False, **kwargs):
    """PUT a un servicio externo, con fingerprint de browser real.

    Agregado el 16/ago/2026 al migrar MercadoPago: el hub cancela suscripciones
    con `PUT /preapproval/{id}`, y sin esto la migración quedaba a medias o
    tenía que importar curl_cffi por su cuenta en un servicio que ya depende de
    aerocommons -- justo lo que este módulo existe para evitar.
    """
    return request("PUT", url, impersonate=impersonate, http3=http3, **kwargs)


def request(method: str, url: str, *, impersonate: str = DEFAULT_IMPERSONATE,
            http3: bool = False, **kwargs):
    """Cualquier verbo, para los casos que `get`/`post`/`put` no cubren.

    Existe para que agregar un método nuevo no obligue a saltarse este módulo:
    la regla dura es que **nada** salga con `requests` pelado, así que el
    escape tiene que estar acá adentro y no en cada servicio.
    """
    if http3:
        kwargs["http_version"] = CurlHttpVersion.V3
    return _curl.request(method, url, impersonate=impersonate, **kwargs)
