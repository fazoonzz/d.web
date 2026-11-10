"""Utilidades de seguridad puras (sin FastAPI) para que se puedan probar de forma unitaria.

- Hash adaptativo de contraseñas con sal (scrypt, stdlib).
- Carga de secretos desde Vault (o variables de entorno SECRET_* para desarrollo local).
- Firma/verificación HMAC de webhooks con ventana de tiempo.
- Limitador de solicitudes por ventana deslizante.
"""
import base64
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.request
from collections import defaultdict, deque

_N, _R, _P = 2 ** 14, 8, 1


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P,
                        dklen=32, maxmem=64 * 1024 * 1024)
    return f"scrypt${_N}${_R}${_P}${_b64(salt)}${_b64(dk)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt, dk = stored.split("$")
        if algo != "scrypt":
            return False
        calc = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt),
                              n=int(n), r=int(r), p=int(p), dklen=32,
                              maxmem=64 * 1024 * 1024)
        return hmac.compare_digest(calc, base64.b64decode(dk))
    except Exception:
        return False


# Hash ficticio para igualar el tiempo de respuesta cuando el usuario no existe.
DUMMY_HASH = hash_password("contraseña-ficticia-para-igualar-tiempos")


def load_secrets(service: str) -> dict:
    """Lee secret/data/<service> de Vault con el token propio del servicio.

    Sin VAULT_TOKEN (desarrollo local) lee variables SECRET_<CLAVE>, p. ej.
    SECRET_FROM_GATEWAY -> {"from_gateway": ...}. Nunca se registran valores en logs.
    """
    token = os.getenv("VAULT_TOKEN")
    if not token:
        return {k[7:].lower(): v for k, v in os.environ.items() if k.startswith("SECRET_")}
    addr = os.getenv("VAULT_ADDR", "http://vault:8200")
    req = urllib.request.Request(f"{addr}/v1/secret/data/{service}",
                                 headers={"X-Vault-Token": token})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())["data"]["data"]


def sign_webhook(secret: str, ts: str, body: bytes) -> str:
    return hmac.new(secret.encode(), ts.encode() + b"." + body, hashlib.sha256).hexdigest()


def verify_webhook(secret: str, ts: str, body: bytes, signature: str,
                   now: float | None = None, tolerance: int = 300) -> bool:
    try:
        if abs((now if now is not None else time.time()) - int(ts)) > tolerance:
            return False
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(sign_webhook(secret, ts, body), signature or "")


class RateLimiter:
    """Ventana deslizante en memoria (suficiente para una instancia de gateway)."""

    def __init__(self):
        self.hits = defaultdict(deque)

    def allow(self, key: str, limit: int, window: float = 60.0, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        q = self.hits[key]
        while q and q[0] <= now - window:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True
