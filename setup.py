from setuptools import setup, find_packages

setup(
    name="aerocommons",
    version="0.2.0",
    packages=find_packages(),
    author="Federico Perez Diduch",
    author_email="fperezdiduch@gmail.com",
    description="Common utilities for Aerobot",
    long_description="",
    url="https://github.com/aerodiduch/aerocommons",
    python_requires=">=3.10",
    # curl_cffi: cliente HTTP para todo lo que sale hacia afuera (aerocommons.http).
    # Requiere Python >=3.10, de ahí el bump -- todos los servicios de Aerobot
    # corren python:3.11-slim, verificado el 15/ago/2026.
    install_requires=["requests", "curl_cffi>=0.16.0"],
)
