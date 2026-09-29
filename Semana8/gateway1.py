import os
import secrets
from fastapi.middleware.cors import CORSMiddleware
import httpx


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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BACKEND_URL = "http://localhost:9000"

if not VAULT_TOKEN:  
    raise RuntimeError(
        "VAULT_TOKEN no esta configurado"
    )

#Obtenemos el secreto del backend desde Vault
async def get_gateway_secret():
    url = (
        f"{VAULT_ADDR}"
        "/v1/secret/data/backend_api"
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

async def authenticate_client(
    credentials:
        HTTPAuthorizationCredentials
        = Depends(security)
):
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="No se proporcionó un token de autorización"
        )
    vault_secrets = (
        await get_gateway_secret()
    )
    expected_token = vault_secrets[
        "client_token"
    ]
    recieved_token = credentials.credentials

    valid = secrets.compare_digest(
        recieved_token,
        expected_token
    )

    if not valid:
        raise HTTPException(
            status_code=403,
            detail="Token de autorización inválido"
        )
    return {
        "client_id": "student_client",
        "backend_secret": vault_secrets[
            "backend_shared_secret"
        ]
    }
#@app.get("/api/products")
#async def products():
#    async with httpx.AsyncClient() as client:
#        response = await client.get(f"{BACKEND_URL}/products")
#    return response.json()

@app.api_route(
    "/api/{path:path}"
    , methods=[
        "GET",
        "POST",
        "PUT",
        "DELETE"
        ]
)

async def proxy(
    path: str,
    request: Request,
    auth= Depends(authenticate_client)
):
    target_url = (
        f"{BACKEND_URL}/{path}"
    )
    body = await request.body()

    gateway_headers = {
        "X-Gateway-Secret": 
        auth["backend_secret"],
        "X-Authenticated-Client":
        auth["client_id"]
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

    response_headers = {}

    