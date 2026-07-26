"""SSL/TLS helpers for verified HTTPS connections."""

from __future__ import annotations

import os
import ssl
import sys
from functools import lru_cache

import certifi

_truststore_injected = False


def _ensure_truststore() -> None:
    """Use the OS certificate store (required on Windows with AV SSL scanning)."""
    global _truststore_injected
    if _truststore_injected:
        return

    if sys.platform == "win32":
        import truststore

        truststore.inject_into_ssl()

    _truststore_injected = True


@lru_cache(maxsize=1)
def create_ssl_context() -> ssl.SSLContext:
    """
    Build a verified SSL context.

    Combines:
    - OS trust store on Windows (antivirus / corporate roots)
    - Mozilla CA bundle from certifi
    - Optional extra bundle from SSL_CA_BUNDLE
    """
    _ensure_truststore()

    context = ssl.create_default_context()
    context.load_verify_locations(cafile=certifi.where())

    extra_ca_bundle = os.getenv("SSL_CA_BUNDLE", "").strip()
    if extra_ca_bundle:
        context.load_verify_locations(cafile=extra_ca_bundle)

    return context


def certifi_bundle_path() -> str:
    """Return the path to the certifi CA bundle."""
    return certifi.where()
