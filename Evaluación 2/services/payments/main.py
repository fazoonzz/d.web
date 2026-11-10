"""payments: inicio de pagos y confirmación mediante webhook firmado del proveedor.

* El monto sale SIEMPRE del pedido (orders), nunca del navegador.
* El aviso del proveedor se verifica con HMAC + marca de tiempo y es idempotente (event_id).
* Solo este servicio le pide a orders marcar un pedido como PAGADO.
* Proveedor: adaptador "sandbox" que conserva el contrato (webhook firmado). Se activa con
  PAYMENT_SANDBOX=true y debe quedar desactivado en producción.
"""
import json
import os
import time
import uuid
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

from common.security import sign_webhook, verify_webhook
from common.svc import (call_sync, caller_dependency, connect, get_secrets, install_common,
                        page, user_dependency)

SERVICE = "payments"
DB = os.getenv("PAYMENTS_DB", "./data/payments.db")
ORDERS_URL = os.getenv("ORDERS_URL", "http://localhost:9003")
SANDBOX = os.getenv("PAYMENT_SANDBOX", "false").lower() == "true"

user_dep = user_dependency(SERVICE, allowed=("gateway",))
gateway_dep = caller_dependency(SERVICE, {"gateway"})   # el webhook llega por el gateway sin sesión

app = FastAPI(title="Payments Service (privado)")
install_common(app, SERVICE)


class StartIn(BaseModel):
    order_id: str = Field(min_length=10, max_length=64)


class SandboxIn(BaseModel):
    resultado: str = Field(pattern="^(approved|rejected)$")


with connect(DB) as _c:
    _c.executescript("""
    CREATE TABLE IF NOT EXISTS payments(
      id TEXT PRIMARY KEY, order_id TEXT NOT NULL, cliente_id TEXT NOT NULL, monto INTEGER NOT NULL,
      estado TEXT NOT NULL CHECK(estado IN('INICIADO','APROBADO','RECHAZADO')),
      proveedor TEXT NOT NULL, creado INTEGER NOT NULL, actualizado INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS webhook_events(event_id TEXT PRIMARY KEY, payment_id TEXT NOT NULL, recibido INTEGER NOT NULL);
    CREATE INDEX IF NOT EXISTS ix_pay_order ON payments(order_id);
    """)


def orders(method, path, **kw):
    return call_sync(ORDERS_URL, method, path, caller=SERVICE,
                     key=get_secrets(SERVICE).get("to_orders", ""), **kw)


def _pay(r):
    return {"id": r["id"], "order_id": r["order_id"], "monto": r["monto"],
            "estado": r["estado"], "proveedor": r["proveedor"], "creado": r["creado"]}


@app.post("/payments", status_code=201)
def start_payment(body: StartIn, user=Depends(user_dep)):
    r = orders("GET", f"/internal/orders/{body.order_id}")
    if r.status_code == 404:
        raise HTTPException(404, "Pedido no encontrado")
    if r.status_code >= 300:
        raise HTTPException(503, "Pedidos no disponible")
    order = r.json()
    if order["cliente_id"] != user.user_id:       # propiedad verificada en el servidor
        raise HTTPException(404, "Pedido no encontrado")
    if order["estado"] != "PENDIENTE_PAGO":
        raise HTTPException(409, f"El pedido está en estado {order['estado']}")
    with connect(DB) as c:
        prev = c.execute("SELECT * FROM payments WHERE order_id=? AND estado='INICIADO'", (body.order_id,)).fetchone()
        if prev:
            return _pay(prev)
        pid, now = str(uuid.uuid4()), int(time.time())
        c.execute("INSERT INTO payments VALUES(?,?,?,?,'INICIADO','sandbox',?,?)",
                  (pid, body.order_id, user.user_id, order["total"], now, now))
        return _pay(c.execute("SELECT * FROM payments WHERE id=?", (pid,)).fetchone())


@app.get("/payments/{payment_id}")
def get_payment(payment_id: str, user=Depends(user_dep)):
    with connect(DB) as c:
        r = c.execute("SELECT * FROM payments WHERE id=?", (payment_id,)).fetchone()
    if not r or (not user.is_admin and r["cliente_id"] != user.user_id):
        raise HTTPException(404, "Pago no encontrado")
    return _pay(r)


def process_event(event: dict) -> dict:
    """Aplica un evento ya verificado. Idempotente por event_id y por estado del pago."""
    with connect(DB) as c:
        if c.execute("SELECT 1 FROM webhook_events WHERE event_id=?", (event["event_id"],)).fetchone():
            return {"duplicado": True}
        p = c.execute("SELECT * FROM payments WHERE id=?", (event["payment_id"],)).fetchone()
        if not p:
            raise HTTPException(404, "Pago desconocido")
        if p["estado"] != "INICIADO":
            return {"duplicado": True}
        if event["monto"] != p["monto"]:                # datos alterados: se rechaza sin cambiar nada
            raise HTTPException(409, "El monto del evento no coincide con el pago")
        nuevo = "APROBADO" if event["tipo"] == "payment.approved" else "RECHAZADO"
        if nuevo == "APROBADO":
            r = orders("POST", f"/internal/orders/{p['order_id']}/mark-paid",
                       json={"payment_id": p["id"], "monto": p["monto"]})
            if r.status_code >= 500:
                raise HTTPException(503, "Pedidos no disponible; el proveedor reintentará")
            if r.status_code >= 300:
                raise HTTPException(409, "El pedido no admite este pago")
        now = int(time.time())
        c.execute("UPDATE payments SET estado=?, actualizado=? WHERE id=?", (nuevo, now, p["id"]))
        c.execute("INSERT OR IGNORE INTO webhook_events VALUES(?,?,?)", (event["event_id"], p["id"], now))
    return {"estado": nuevo}


@app.post("/payments/webhook")
async def webhook(request: Request, caller=Depends(gateway_dep),
                  x_signature: str = Header(default=""), x_timestamp: str = Header(default="")):
    body = await request.body()
    secret = get_secrets(SERVICE).get("webhook_secret", "")
    if not secret or not verify_webhook(secret, x_timestamp, body, x_signature):
        raise HTTPException(401, "Firma inválida")
    try:
        event = json.loads(body)
        assert event["tipo"] in ("payment.approved", "payment.rejected")
        event = {"event_id": str(event["event_id"]), "payment_id": str(event["payment_id"]),
                 "tipo": event["tipo"], "monto": int(event["monto"])}
    except Exception:
        raise HTTPException(422, "Evento inválido")
    return process_event(event)


@app.post("/payments/{payment_id}/sandbox-resolve")
def sandbox_resolve(payment_id: str, body: SandboxIn, user=Depends(user_dep)):
    """Simula al proveedor: construye un evento firmado y lo procesa por el mismo camino del webhook."""
    if not SANDBOX:
        raise HTTPException(404, "No encontrado")
    with connect(DB) as c:
        p = c.execute("SELECT * FROM payments WHERE id=?", (payment_id,)).fetchone()
    if not p or p["cliente_id"] != user.user_id:
        raise HTTPException(404, "Pago no encontrado")
    secret = get_secrets(SERVICE).get("webhook_secret", "")
    raw = json.dumps({"event_id": str(uuid.uuid4()), "payment_id": p["id"], "monto": p["monto"],
                      "tipo": "payment.approved" if body.resultado == "approved" else "payment.rejected"}).encode()
    ts = str(int(time.time()))
    assert verify_webhook(secret, ts, raw, sign_webhook(secret, ts, raw))
    return process_event(json.loads(raw))
