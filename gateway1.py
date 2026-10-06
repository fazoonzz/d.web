import os
import secrets
from fastapi.middleware.cors import CORSMiddleware
import httpx
from pydantic import BaseModel

from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Request,
    Response,
)

from fastapi.security import (
    HTTPBearer,
    HTTPAuthorizationCredentials
)


app = FastAPI(
    title="Local API Gateway"
    )

security = HTTPBearer(
    auto_error=False
    )

AUTH_SERVICE_URL = os.getenv(
    "AUTH_SERVICE_URL",
    "http://localhost:8100" 
)
VAULT_ADDR = os.getenv(
    "VAULT_ADDR",
    "http://127.0.0.1:8200"
)

VAULT_TOKEN = os.getenv(
    "VAULT_TOKEN"
)

# Permite que index.php consuma este endpoint sin problemas de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1","http://localhost:8100", "http://localhost:8000"  ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BACKEND_URL = "http://localhost:9000"

if not VAULT_TOKEN:  
    raise RuntimeError(
        "VAULT_TOKEN no esta configurado"
    )

class LoginPayload(BaseModel):
    username: str
    password: str

#Obtenemos el secreto del backend desde Vault
async def get_gateway_secret():
    url = (
        f"{VAULT_ADDR}"
        "/v1/secret/data/gateway"
    )
    headers = {
        "X-Vault-Token": VAULT_TOKEN
    }

    async with httpx.AsyncClient(
        timeout=10.0
    ) as client:
        response = await client.get(
            url,
            headers=headers
        )
    if response.status_code != 200:
        raise HTTPException(
            status_code=500,
            detail="Error al obtener el secreto del backend desde Vault"
        )
    vault_response = response.json()
    return vault_response[
        "data"
        ][
        "data"
        ]

@app.post("/auth/login")
async def login(payload: LoginPayload, response: Response):
    secrets_data = await get_gateway_secret()
    async with httpx.AsyncClient(timeout=5.0) as client:
        res = await client.post(
            f"{AUTH_SERVICE_URL}/login",
            json=payload.model_dump(),
            headers={"X-Gateway-Auth-Secret": secrets_data.get("auth_introspection_secret")}
        )
    if res.status_code != 200:
        raise HTTPException(status_code=res.status_code, detail="Credenciales incorrectas")

    token_info = res.json()
    token = token_info.get("access_token")

    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=token_info.get("expires_in", 900)
    )
    return {"message": "Login exitoso"}

@app.post("/auth/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if token:
        secrets_data = await get_gateway_secret()
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{AUTH_SERVICE_URL}/logout",
                json={"token": token},
                headers={"X-Gateway-Auth-Secret": secrets_data.get("auth_introspection_secret")}
            )
    response.delete_cookie("session_token")
    return {"message": "Sesión cerrada"}

async def authenticate_session(request: Request):
    # 1. Busca primero la cookie HttpOnly
    token = request.cookies.get("session_token")
    
    # 2. Si no hay cookie, busca el header Authorization Bearer (para pruebas Postman / curl)
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        raise HTTPException(
            status_code=401,
            detail="No se proporcionó un token de autorización ni sesión activa"
        )

    gateway_secrets = await get_gateway_secret()
    introspection_secret = gateway_secrets.get("auth_introspection_secret")

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{AUTH_SERVICE_URL}/introspect",
                json={"token": token},
                headers={"X-Gateway-Auth-Secret": introspection_secret}
            )
    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="Servicio de autenticación no disponible"
        )

    identity = response.json()
    if not identity.get("active", False):
        raise HTTPException(
            status_code=401,
            detail="Token inválido o sesión expirada"
        )

    return {
        "client_id": "student_client",
        "user_id": identity.get("user_id"),
        "username": identity.get("username"),
        "roles": identity.get("roles", []),
        "backend_secret": gateway_secrets.get("backend_shared_secret")
    }


#@app.get("/api/products")
#async def products():
#    async with httpx.AsyncClient() as client:
#        response = await client.get(f"{BACKEND_URL}/products")
#    return response.json()

@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy(path: str, request: Request, auth=Depends(authenticate_session)):
    target_url = f"{BACKEND_URL}/{path}"
    body = await request.body()

    gateway_headers = {
        "X-Gateway-Secret": 
        auth["backend_secret"],
        "X-Authenticated-Client":
        auth["client_id"],
        "X-Authenticated-User":
        auth["username"],
        "X-Authenticated-Roles":
        ",".join(auth["roles"])
    }

    content_type = request.headers.get( 
        "content-type"
    )
    if content_type:
        gateway_headers[
            "Content-Type"
        ] = content_type
    try:
        async with httpx.AsyncClient(
        timeout=10.0
        ) as client:
            upstream = await client.request(
                method=request.method,
                url=target_url,
                params=request.query_params,
                content=body,
                headers=gateway_headers
            )
    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail=f"Backend no disponible"
        )

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=dict(upstream.headers)
    )

    