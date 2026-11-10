"""clients: perfil y datos personales del cliente (autoridad de nombre, teléfono y dirección).

No se almacena RUN: el negocio no lo necesita para vender y entregar tortas (minimización).
"""
import os
import time
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from common.svc import (admin_dependency, caller_dependency, connect, install_common,
                        page, user_dependency)

SERVICE = "clients"
DB = os.getenv("CLIENTS_DB", "./data/clients.db")

user_dep = user_dependency(SERVICE)                       # gateway o graphql, con identidad
admin_dep = admin_dependency(user_dep)
auth_only = caller_dependency(SERVICE, {"auth"})          # alta/baja de perfil: solo auth

app = FastAPI(title="Clients Service (privado)")
install_common(app, SERVICE)


class ProfileIn(BaseModel):  # PUT reemplaza la representación completa
    nombre: str = Field(min_length=2, max_length=80)
    telefono: Optional[str] = Field(default=None, pattern=r"^\+?[0-9 ]{8,15}$")
    direccion: Optional[str] = Field(default=None, min_length=5, max_length=200)


class NewClient(BaseModel):
    user_id: str = Field(min_length=10, max_length=64)
    email: str = Field(max_length=254)
    nombre: str = Field(min_length=2, max_length=80)


with connect(DB) as _c:
    _c.execute("""CREATE TABLE IF NOT EXISTS clients(
        user_id TEXT PRIMARY KEY, email TEXT NOT NULL, nombre TEXT NOT NULL,
        telefono TEXT, direccion TEXT, creado INTEGER NOT NULL)""")


def _row(r, full=True):
    d = {"id": r["user_id"], "email": r["email"], "nombre": r["nombre"]}
    if full:
        d.update({"telefono": r["telefono"], "direccion": r["direccion"]})
    return d


@app.get("/clients/me")
def get_me(user=Depends(user_dep)):
    with connect(DB) as c:
        r = c.execute("SELECT * FROM clients WHERE user_id=?", (user.user_id,)).fetchone()
        if not r:  # usuarios sembrados: perfil mínimo creado al primer acceso
            c.execute("INSERT INTO clients VALUES(?,?,?,NULL,NULL,?)",
                      (user.user_id, user.email, user.email.split("@")[0][:80] or "Cliente", int(time.time())))
            r = c.execute("SELECT * FROM clients WHERE user_id=?", (user.user_id,)).fetchone()
    return _row(r)


@app.put("/clients/me")
def put_me(body: ProfileIn, user=Depends(user_dep)):
    with connect(DB) as c:
        n = c.execute("UPDATE clients SET nombre=?, telefono=?, direccion=? WHERE user_id=?",
                      (body.nombre, body.telefono, body.direccion, user.user_id)).rowcount
        if not n:
            raise HTTPException(404, "Perfil no encontrado")
        r = c.execute("SELECT * FROM clients WHERE user_id=?", (user.user_id,)).fetchone()
    return _row(r)


@app.get("/clients")
def list_clients(limit: int = 20, offset: int = 0, user=Depends(admin_dep)):
    limit, offset = page(limit, offset)
    with connect(DB) as c:
        rows = c.execute("SELECT * FROM clients ORDER BY creado DESC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
    return [_row(r, full=False) for r in rows]   # el listado no incluye teléfono ni dirección


@app.get("/clients/{client_id}")
def get_client(client_id: str, user=Depends(admin_dep)):
    with connect(DB) as c:
        r = c.execute("SELECT * FROM clients WHERE user_id=?", (client_id,)).fetchone()
    if not r:
        raise HTTPException(404, "Cliente no encontrado")
    return _row(r)


@app.post("/internal/clients", status_code=201)
def create_client(body: NewClient, caller=Depends(auth_only)):
    with connect(DB) as c:
        c.execute("INSERT OR IGNORE INTO clients VALUES(?,?,?,NULL,NULL,?)",
                  (body.user_id, body.email, body.nombre, int(time.time())))
    return {"id": body.user_id}
