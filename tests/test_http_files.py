"""`files=` de requests traducido a `multipart` de curl_cffi.

curl_cffi rechaza `files=` con NotImplementedError, y lo hace **en runtime**:
el servicio arranca bien y falla recién cuando alguien usa la función. El
16/ago/2026 eso rompió la subida del video del radar a Meta durante un deploy
que parecía limpio -- 0 errores de import, 0 reinicios, y el bot contestando
"hubo un problema al procesar el video".
"""
import io

import pytest

from aerocommons import http


def test_traduce_una_tupla_con_nombre_y_content_type():
    mp = http._traducir_files({"file": ("radar.mp4", b"datos", "video/mp4")})
    assert mp is not None  # CurlMime no expone sus partes; que construya alcanza


def test_traduce_un_file_object_abierto():
    mp = http._traducir_files({"file": ("radar.mp4", io.BytesIO(b"datos"), "video/mp4")})
    assert mp is not None


def test_traduce_bytes_pelados():
    assert http._traducir_files({"file": b"datos"}) is not None


def test_post_convierte_files_en_multipart(monkeypatch):
    """Lo que importa: que `post` no le pase `files` a curl_cffi."""
    visto = {}

    def falso(url, **kwargs):
        visto.update(kwargs)
        return "ok"

    monkeypatch.setattr(http._curl, "post", falso)
    http.post("https://ejemplo.com", files={"file": ("a.mp4", b"x", "video/mp4")})

    assert "files" not in visto, "curl_cffi levanta NotImplementedError si le llega `files`"
    assert "multipart" in visto


def test_post_sin_files_no_toca_nada(monkeypatch):
    visto = {}
    monkeypatch.setattr(http._curl, "post", lambda url, **kw: visto.update(kw) or "ok")
    http.post("https://ejemplo.com", json={"a": 1})
    assert "multipart" not in visto
    assert visto["json"] == {"a": 1}
