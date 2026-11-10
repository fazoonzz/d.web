import logging
import os
import time
import uuid

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from common.security import RateLimiter, load_secrets
from gateway.routes import known_path, match

log = logging.getLogger("gateway")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

URLS = {
    "auth": os.getenv("AUTH_URL", "http://localhost:8100"),
    "clients": os.getenv("CLIENTS_URL", "http://localhost:9001"),
    "inventory": os.getenv("INVENTORY_URL", "http://localhost:9002"),
    "orders": os.getenv("ORDERS_URL", "http://localhost:9003"),
    "payments": os.getenv("PAYMENTS_URL", "http://localhost:9004"),
    "graphql": os.getenv("GRAPHQL_URL", "http://localhost:8090"),
}
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080").split(",") if o.strip()]
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
MAX_BODY = 64 * 1024
LIMITS = {"default": 100000, "auth": 100000, "webhook": 60}  
TIMEOUT = httpx.Timeout(8.0, connect=2.0)

app = FastAPI(title="API Gateway", docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True,
                   allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Content-Type"])
limiter = RateLimiter()
_secrets = {"t": 0.0, "v": {}}


def secrets_now() -> dict:
    if time.time() - _secrets["t"] > 300 or not _secrets["v"]:
        try:
            _secrets["v"], _secrets["t"] = load_secrets("gateway"), time.time()
        except Exception:
            if not _secrets["v"]:
                raise
            log.warning("Vault no responde")
    return _secrets["v"]


def err(status: int, detail: str, cid: str = "-") -> JSONResponse:
    return JSONResponse({"detail": detail}, status_code=status, headers={"X-Correlation-Id": cid})


async def call_auth(path: str, payload: dict, cid: str):
    return await _post(path, payload, "auth", cid)


async def _post(path, payload, service, cid):
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        return await client.post(f"{URLS[service]}{path}", json=payload, headers={
            "X-Service-Name": "gateway", "X-Service-Key": secrets_now().get(f"to_{service}", ""),
            "X-Correlation-Id": cid})


async def identity_from(request: Request, cid: str):
    token = request.cookies.get("session_token")
    if not token:
        return None
    r = await call_auth("/introspect", {"token": token}, cid)
    data = r.json() if r.status_code == 200 else {}
    return data if data.get("active") else None


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "?"


def too_many(request: Request, bucket: str, cid: str):
    if not limiter.allow(f"{client_ip(request)}:{bucket}", LIMITS[bucket]):
        return err(429, "Demasiadas solicitudes", cid)


def set_cookie(response, token: str, max_age: int):
    response.set_cookie("session_token", token, max_age=max_age, httponly=True, secure=COOKIE_SECURE,
                        samesite="lax", path="/")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "gateway"}


@app.post("/api/v1/auth/register", status_code=201)
async def register(request: Request):
    cid = uuid.uuid4().hex[:16]
    if (r := too_many(request, "auth", cid)):
        return r
    body = await request.body()
    if len(body) > MAX_BODY:
        return err(413, "Solicitud demasiado grande", cid)
    try:
        import json
        payload = json.loads(body)
        payload = {k: payload[k] for k in ("email", "password", "nombre")} 
    except Exception:
        return err(422, "Datos de registro inválidos", cid)
    try:
        res = await call_auth("/register", payload, cid)
    except httpx.RequestError:
        return err(502, "Servicio de autenticación no disponible", cid)
    return JSONResponse(res.json() if res.status_code < 500 else {"detail": "Error interno del servicio"},
                        status_code=res.status_code, headers={"X-Correlation-Id": cid})


@app.post("/api/v1/auth/login")
async def login(request: Request):
    cid = uuid.uuid4().hex[:16]
    if (r := too_many(request, "auth", cid)):
        return r
    body = await request.body()
    try:
        import json
        p = json.loads(body)
        payload = {"email": str(p["email"]), "password": str(p["password"])}
    except Exception:
        return err(422, "Datos de acceso incorrectos", cid)
    try:
        res = await call_auth("/login", payload, cid)
    except httpx.RequestError:
        return err(502, "Servicio de autenticación no disponible", cid)
    if res.status_code != 200:
        return err(res.status_code if res.status_code < 500 else 502,
                   res.json().get("detail", "Error") if res.status_code < 500 else "Servicio no disponible", cid)
    info = res.json()
    out = JSONResponse({"message": "Login exitoso", "user": {"email": info["user"]["email"], "roles": info["user"]["roles"]}},
                       headers={"X-Correlation-Id": cid})
    set_cookie(out, info["access_token"], info["expires_in"]) 
    return out


@app.post("/api/v1/auth/logout")
async def logout(request: Request):
    cid = uuid.uuid4().hex[:16]
    token = request.cookies.get("session_token")
    if token:
        try:
            await call_auth("/logout", {"token": token}, cid)
        except httpx.RequestError:
            pass
    out = JSONResponse({"message": "Sesión cerrada"}, headers={"X-Correlation-Id": cid})
    out.delete_cookie("session_token", path="/")
    return out


@app.get("/api/v1/auth/me")
async def me(request: Request):
    cid = uuid.uuid4().hex[:16]
    try:
        ident = await identity_from(request, cid)
    except httpx.RequestError:
        return err(502, "Servicio de autenticación no disponible", cid)
    if not ident:
        return err(401, "Sesión no válida", cid)
    return {"email": ident["email"], "roles": ident["roles"]}


@app.api_route("/api/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy(path: str, request: Request):
    cid = request.headers.get("x-correlation-id") or uuid.uuid4().hex[:16]
    start = time.time()
    m = match(request.method, "/" + path)
    if not m:
        return err(405 if known_path("/" + path) else 404, "Ruta no disponible", cid)
    route, params = m
    if (r := too_many(request, route.limit, cid)):
        return r

    ident = None
    if route.access == "anon":
        if request.cookies.get("session_token"):
            try:
                ident = await identity_from(request, cid)
            except httpx.RequestError:
                ident = None
    else:
        try:
            ident = await identity_from(request, cid)
        except httpx.RequestError:
            return err(502, "Servicio de autenticación no disponible", cid)
        if not ident:
            return err(401, "Sesión no válida o expirada", cid)
        if route.access == "admin" and "admin" not in ident["roles"]:
            return err(403, "Operación denegada", cid)

    body = await request.body()
    if len(body) > MAX_BODY:
        return err(413, "Solicitud demasiado grande", cid)

    headers = {"X-Service-Name": "gateway", "X-Service-Key": secrets_now().get(f"to_{route.service}", ""),
               "X-Correlation-Id": cid}
    if ident:
        headers.update({"X-User-Id": ident["user_id"], "X-User-Email": ident["email"],
                        "X-User-Roles": ",".join(ident["roles"])})
    if request.headers.get("content-type"):
        headers["Content-Type"] = request.headers["content-type"]
    for h in route.extra_headers:
        if request.headers.get(h):
            headers[h] = request.headers[h]

    target = route.target
    for k, v in params.items():
        target = target.replace("{" + k + "}", v)
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            up = await client.request(request.method, f"{URLS[route.service]}{target}",
                                      params=dict(request.query_params), content=body, headers=headers)
    except httpx.TimeoutException:
        return err(504, "Tiempo de espera agotado", cid)
    except httpx.RequestError:
        return err(502, "Servicio no disponible", cid)

    log.info("gateway cid=%s %s /%s -> %s %s %.0fms", cid, request.method, path, route.service,
             up.status_code, (time.time() - start) * 1000)
    if up.status_code >= 500:
        return err(502, "Error interno del servicio", cid)
    return Response(up.content, status_code=up.status_code,
                    media_type=up.headers.get("content-type", "application/json"),
                    headers={"X-Correlation-Id": cid})
