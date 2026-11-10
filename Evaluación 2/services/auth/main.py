"""auth: credenciales, sesiones y emisión de tokens opacos. Solo lo llama el gateway.

Datos bajo su autoridad: usuarios (email, hash de contraseña, roles) y sesiones.
Los tokens se guardan como SHA-256 (si se filtra la BD, no sirven como sesión).
"""
import hashlib
import os
import re
import secrets
import time
import uuid

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from common.security import DUMMY_HASH, hash_password, verify_password
from common.svc import (caller_dependency, call_sync, connect, get_secrets,
                        install_common, log, transaction)

SERVICE = "auth"
DB = os.getenv("AUTH_DB", "./data/auth.db")
TOKEN_MIN = int(os.getenv("TOKEN_LIFETIME_MIN", "15"))
CLIENTS_URL = os.getenv("CLIENTS_URL", "http://localhost:9001")
MAX_FAILS, LOCK_SECONDS = 5, 300

only_gateway = caller_dependency(SERVICE, {"gateway"})
app = FastAPI(title="Auth Service (privado)")
install_common(app, SERVICE)
_fails: dict[str, tuple[int, float]] = {}  # email -> (intentos, bloqueado_hasta)

EMAIL = r"^[^@\s]{1,64}@[^@\s]{1,200}\.[^@\s]{2,}$"


class RegisterIn(BaseModel):
    email: str = Field(pattern=EMAIL, max_length=254)
    password: str = Field(min_length=10, max_length=128)
    nombre: str = Field(min_length=2, max_length=80)


class LoginIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)


class TokenIn(BaseModel):
    token: str = Field(min_length=20, max_length=200)


def _th(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def init_db():
    with connect(DB) as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(
          user_id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL,
          password_hash TEXT NOT NULL, roles TEXT NOT NULL,
          activo INTEGER NOT NULL DEFAULT 1, creado INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(
          token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(user_id),
          expires_at INTEGER NOT NULL, creado INTEGER NOT NULL);
        """)
        # Usuarios semilla desde variables de entorno (nunca desde el código).
        for prefix, roles in (("SEED_ADMIN", "admin"), ("SEED_CLIENT", "cliente")):
            email, pw = os.getenv(f"{prefix}_EMAIL"), os.getenv(f"{prefix}_PASSWORD")
            if email and pw and not c.execute("SELECT 1 FROM users WHERE email=?", (email.lower(),)).fetchone():
                c.execute("INSERT INTO users VALUES(?,?,?,?,1,?)",
                          (str(uuid.uuid4()), email.lower(), hash_password(pw), roles, int(time.time())))


init_db()


@app.post("/register", status_code=201)
def register(body: RegisterIn, caller=Depends(only_gateway)):
    email = body.email.lower()
    user_id = str(uuid.uuid4())
    with connect(DB) as c:
        if c.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            raise HTTPException(409, "El correo ya está registrado")
        c.execute("INSERT INTO users VALUES(?,?,?,?,1,?)",
                  (user_id, email, hash_password(body.password), "cliente", int(time.time())))
    # El perfil vive en clients (autoridad de datos personales). Si falla, se compensa.
    r = call_sync(CLIENTS_URL, "POST", "/internal/clients", caller=SERVICE,
                  key=get_secrets(SERVICE).get("to_clients", ""),
                  json={"user_id": user_id, "email": email, "nombre": body.nombre})
    if r.status_code >= 300:
        with connect(DB) as c:
            c.execute("DELETE FROM users WHERE user_id=?", (user_id,))
        raise HTTPException(502, "No se pudo crear el perfil del cliente")
    return {"user_id": user_id, "email": email}


@app.post("/login")
def login(body: LoginIn, caller=Depends(only_gateway)):
    email = body.email.lower()
    fails, locked_until = _fails.get(email, (0, 0.0))
    if locked_until > time.time():
        raise HTTPException(429, "Demasiados intentos. Intenta más tarde")
    with connect(DB) as c:
        u = c.execute("SELECT * FROM users WHERE email=? AND activo=1", (email,)).fetchone()
        ok = verify_password(body.password, u["password_hash"] if u else DUMMY_HASH) and u is not None
        if not ok:
            fails += 1
            _fails[email] = (fails, time.time() + LOCK_SECONDS if fails >= MAX_FAILS else 0.0)
            raise HTTPException(401, "Credenciales inválidas")  # mismo mensaje exista o no el usuario
        _fails.pop(email, None)
        token = secrets.token_urlsafe(32)
        now = int(time.time())
        c.execute("DELETE FROM sessions WHERE expires_at<?", (now,))
        c.execute("INSERT INTO sessions VALUES(?,?,?,?)", (_th(token), u["user_id"], now + TOKEN_MIN * 60, now))
    return {"access_token": token, "expires_in": TOKEN_MIN * 60,
            "user": {"user_id": u["user_id"], "email": u["email"], "roles": u["roles"].split(",")}}


@app.post("/introspect")
def introspect(body: TokenIn, caller=Depends(only_gateway)):
    with connect(DB) as c:
        row = c.execute("""SELECT u.user_id,u.email,u.roles,s.expires_at FROM sessions s
                           JOIN users u ON u.user_id=s.user_id
                           WHERE s.token_hash=? AND u.activo=1""", (_th(body.token),)).fetchone()
        if not row or row["expires_at"] < time.time():
            return {"active": False}
    return {"active": True, "user_id": row["user_id"], "email": row["email"],
            "roles": row["roles"].split(","), "expires_at": row["expires_at"]}


@app.post("/logout")
def logout(body: TokenIn, caller=Depends(only_gateway)):
    with connect(DB) as c:
        c.execute("DELETE FROM sessions WHERE token_hash=?", (_th(body.token),))
    return {"message": "Sesión cerrada"}
