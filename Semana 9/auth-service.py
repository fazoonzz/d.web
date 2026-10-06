from datetime import datetime, timedelta, timezone
import os
import secrets

from fastapi import (FastAPI, Header, HTTPException)
from httpx import request
from pydantic import BaseModel

app = FastAPI(
    title="Authentication Service",
    description="Servicio de autenticación para la API Gateway y emision de token"
)

USERS = {   
    "testuser": {
        "password": "testuser123",
        "user_id": "user_1",
        "roles": ["user", "admin"]
    },
        "ana": {
        "password": "1234",
        "user_id": "USR-001",
        "roles": ["user"]
    },
        "ernesto": {
        "password": "amdmin123",
        "user_id": "USR-002",
        "roles": ["user", "admin"]
    },
}

SESIONES = {}

TOKEN_LIFETIME_MINUTES = 15

AUTH_INSTROPECTION_SECRET = os.getenv(
    "AUTH_INSTROPECTION_SECRET",
    "demo_intstropection_secret" # gateway-auth-secret-789   
)

class LoginRequest(BaseModel):
    username: str
    password: str

class introspectionRequest(BaseModel):
    token: str

@app.post("/login")
def login(request: LoginRequest,
        x_gateway_auth_secret: str = Header(default="")
        ):
    user = USERS.get(request.username)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Usuario invalido"
        )
    if user["password"] != request.password:
        raise HTTPException(
            status_code=401,
            detail="Contraseña invalida"
        )
    access_token = secrets.token_urlsafe(32)   
    expiration_time = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_LIFETIME_MINUTES)
    SESIONES[access_token] = {
        "user_id": user["user_id"],
        "username": request.username    ,
        "roles": user["roles"],
        "expires_at": expiration_time   
    }
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": TOKEN_LIFETIME_MINUTES * 60
    }

@app.post("/introspect")
def introspect(
    request: introspectionRequest,
    x_gateway_auth_secret: str = Header(default="")
):
    if not secrets.compare_digest(
        x_gateway_auth_secret, 
        AUTH_INSTROPECTION_SECRET
    ):
        raise HTTPException(
            status_code=403,
            detail="Token de autorización inválido"
        )
    session = SESIONES.get(request.token)
    if session is None:
        return {
            "active": False
        }   
    if datetime.now(timezone.utc) > session["expires_at"]:
        SESIONES.pop(request.token, None)
        return {
            "active": False
        }
    return {
        "active": True,
        "user_id": session["user_id"],
        "username": session["username"],
        "roles": session["roles"],
        "expires_at": session["expires_at"].isoformat()
    }

@app.post("/logout")
def logout(
    request: introspectionRequest,
    x_gateway_auth_secret: str = Header(default="")
):
    if not secrets.compare_digest(
        x_gateway_auth_secret, 
        AUTH_INSTROPECTION_SECRET
    ):
        raise HTTPException(
            status_code=403,
            detail="Token de autorización inválido"
        )
    session = SESIONES.get(request.token)
    if session is None:
        return {
            "active": False
        }  
    SESIONES.pop(request.token, None)
    return {
        "message": "Sesión cerrada"
    }
@app.get("/health")
def health(x_gateway_auth_secret: str = Header(default="")
        ):
    if not secrets.compare_digest(
        x_gateway_auth_secret, 
        AUTH_INSTROPECTION_SECRET
    ):
        raise HTTPException(
            status_code=403,
            detail="Token de autorización inválido"
        )
    return {
        "status": "ok",
        "service": "auth-service",  
    }   
