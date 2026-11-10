"""Piezas compartidas por los microservicios FastAPI.

Modelo de confianza entre componentes:
  * Cada llamador se identifica con X-Service-Name + X-Service-Key.
  * Cada servicio guarda una clave DISTINTA por llamador (from_<llamador>) y cada
    llamador guarda su copia (to_<destino>). Un secreto filtrado sirve para un solo tramo.
  * La identidad del usuario (X-User-*) solo se acepta si el llamador es de confianza
    (gateway o graphql). El gateway descarta cualquier X-User-* que envíe el navegador.
"""
import contextvars
import hmac
import logging
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from common.security import load_secrets

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("svc")

cid_var: contextvars.ContextVar[str] = contextvars.ContextVar("cid", default="-")
_cache: dict = {}


def get_secrets(service: str) -> dict:
    now = time.time()
    hit = _cache.get(service)
    if hit and now - hit[0] < 300:
        return hit[1]
    try:
        data = load_secrets(service)
    except Exception:
        if hit:  # Vault no responde: se sigue con la copia previa
            return hit[1]
        raise HTTPException(503, "Gestor de secretos no disponible")
    _cache[service] = (now, data)
    return data


# ----------------------------------------------------------------- autenticación
def caller_dependency(service: str, allowed: set[str]):
    def dep(x_service_name: str = Header(default=""), x_service_key: str = Header(default="")) -> str:
        if x_service_name not in allowed:
            raise HTTPException(403, "Solicitud no autorizada")
        expected = get_secrets(service).get(f"from_{x_service_name}", "")
        if not expected or not hmac.compare_digest(x_service_key.encode(), expected.encode()):
            raise HTTPException(403, "Solicitud no autorizada")
        return x_service_name
    return dep


@dataclass
class Identity:
    user_id: str
    email: str
    roles: list[str]

    @property
    def is_admin(self) -> bool:
        return "admin" in self.roles


def user_dependency(service: str, allowed=("gateway", "graphql")):
    check = caller_dependency(service, set(allowed))

    def dep(caller: str = Depends(check),
            x_user_id: str = Header(default=""),
            x_user_email: str = Header(default=""),
            x_user_roles: str = Header(default="")) -> Identity:
        if not x_user_id:
            raise HTTPException(401, "Identidad no proporcionada")
        roles = [r.strip() for r in x_user_roles.split(",") if r.strip()]
        return Identity(x_user_id, x_user_email, roles)
    return dep


def admin_dependency(user_dep):
    def dep(user: Identity = Depends(user_dep)) -> Identity:
        if not user.is_admin:
            raise HTTPException(403, "Operación denegada: requiere rol admin")
        return user
    return dep


# ------------------------------------------------------------------ llamadas salientes
def call_sync(base_url: str, method: str, path: str, *, caller: str, key: str,
              identity: Identity | None = None, json=None, params=None, timeout: float = 3.0):
    import httpx
    headers = {"X-Service-Name": caller, "X-Service-Key": key, "X-Correlation-Id": cid_var.get()}
    if identity:
        headers.update({"X-User-Id": identity.user_id, "X-User-Email": identity.email,
                        "X-User-Roles": ",".join(identity.roles)})
    try:
        return httpx.request(method, f"{base_url}{path}", headers=headers, json=json,
                             params=params, timeout=timeout)
    except httpx.TimeoutException:
        raise HTTPException(504, "Tiempo de espera agotado en servicio dependiente")
    except httpx.RequestError:
        raise HTTPException(503, "Servicio dependiente no disponible")


# ------------------------------------------------------------------ base de datos
@contextmanager
def connect(path: str):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction(conn):
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def page(limit: int, offset: int) -> tuple[int, int]:
    return max(1, min(limit, 50)), max(0, offset)


# ------------------------------------------------------------------ app base
def install_common(app: FastAPI, name: str) -> None:
    @app.middleware("http")
    async def correlation(request: Request, call_next):
        cid = request.headers.get("x-correlation-id") or uuid.uuid4().hex[:16]
        token = cid_var.set(cid)
        start = time.time()
        try:
            response = await call_next(request)
        finally:
            cid_var.reset(token)
        response.headers["X-Correlation-Id"] = cid
        # Solo método, ruta (sin query) y estado: sin cabeceras, cuerpos ni datos personales.
        log.info("%s cid=%s %s %s -> %s %.0fms", name, cid, request.method,
                 request.url.path, response.status_code, (time.time() - start) * 1000)
        return response

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception):
        log.exception("%s error no controlado", name)
        return JSONResponse({"detail": "Error interno del servicio"}, status_code=500)

    @app.get("/health")
    def health():
        return {"status": "ok", "service": name}
