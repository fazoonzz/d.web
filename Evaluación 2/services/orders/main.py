"""orders: creación y ciclo de vida de pedidos. Autoridad del estado del pedido.

Precios y stock vienen de inventory (nunca del navegador). El estado PAGADO solo lo fija
payments mediante /internal/orders/{id}/mark-paid.
"""
import asyncio
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from common.svc import (call_sync, caller_dependency, connect, get_secrets, install_common,
                        log, page, transaction, user_dependency)
from services.orders import domain as D

SERVICE = "orders"
DB = os.getenv("ORDERS_DB", "./data/orders.db")
INVENTORY_URL = os.getenv("INVENTORY_URL", "http://localhost:9002")
TTL_MIN = int(os.getenv("ORDER_TTL_MIN", "30"))
CL = timezone(timedelta(hours=-3))  # hora de Chile continental (aprox.) para fechas sin zona

user_dep = user_dependency(SERVICE)
payments_dep = caller_dependency(SERVICE, {"payments"})


@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(_expire_loop())
    yield
    task.cancel()


app = FastAPI(title="Orders Service (privado)", lifespan=lifespan)
install_common(app, SERVICE)


class ItemIn(BaseModel):
    product_id: int = Field(ge=1)
    cantidad: int = Field(ge=1, le=10)
    mensaje: Optional[str] = Field(default=None, max_length=60)


class OrderIn(BaseModel):
    items: list[ItemIn] = Field(min_length=1, max_length=20)
    direccion_entrega: str = Field(min_length=5, max_length=200)
    fecha_entrega: datetime
    notas: Optional[str] = Field(default=None, max_length=300)


class StatusIn(BaseModel):
    estado: str


class PaidIn(BaseModel):
    payment_id: str = Field(min_length=10, max_length=64)
    monto: int = Field(ge=1)


with connect(DB) as _c:
    _c.executescript("""
    CREATE TABLE IF NOT EXISTS orders(
      id TEXT PRIMARY KEY, cliente_id TEXT NOT NULL, estado TEXT NOT NULL, total INTEGER NOT NULL,
      direccion_entrega TEXT NOT NULL, fecha_entrega TEXT NOT NULL, notas TEXT,
      payment_id TEXT, creado INTEGER NOT NULL, actualizado INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS order_items(
      order_id TEXT NOT NULL REFERENCES orders(id), product_id INTEGER NOT NULL, nombre TEXT NOT NULL,
      precio_unitario INTEGER NOT NULL, cantidad INTEGER NOT NULL, mensaje TEXT,
      PRIMARY KEY(order_id, product_id));
    CREATE TABLE IF NOT EXISTS order_events(
      id INTEGER PRIMARY KEY AUTOINCREMENT, order_id TEXT NOT NULL REFERENCES orders(id),
      estado TEXT NOT NULL, actor TEXT NOT NULL, ts INTEGER NOT NULL);
    CREATE INDEX IF NOT EXISTS ix_orders_cliente ON orders(cliente_id, creado DESC);
    """)


def inv(method, path, **kw):
    return call_sync(INVENTORY_URL, method, path, caller=SERVICE,
                     key=get_secrets(SERVICE).get("to_inventory", ""), **kw)


def _event(c, order_id, estado, actor):
    c.execute("INSERT INTO order_events(order_id,estado,actor,ts) VALUES(?,?,?,?)",
              (order_id, estado, actor, int(time.time())))


def _order(c, r, admin=False, detail=True):
    d = {"id": r["id"], "estado": r["estado"], "total": r["total"],
         "fecha_entrega": r["fecha_entrega"], "direccion_entrega": r["direccion_entrega"],
         "notas": r["notas"], "creado": r["creado"]}
    if admin:
        d["cliente_id"] = r["cliente_id"]
    if detail:
        d["items"] = [dict(i) for i in c.execute(
            "SELECT product_id,nombre,precio_unitario,cantidad,mensaje FROM order_items WHERE order_id=?", (r["id"],))]
        d["historial"] = [{"estado": e["estado"], "ts": e["ts"]} for e in c.execute(
            "SELECT estado,ts FROM order_events WHERE order_id=? ORDER BY id", (r["id"],))]
    return d


def _get_visible(c, order_id, user):
    r = c.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    # 404 (no 403) para pedidos ajenos: no se revela que el pedido exista.
    if not r or (not user.is_admin and r["cliente_id"] != user.user_id):
        raise HTTPException(404, "Pedido no encontrado")
    return r


# ------------------------------------------------------------------ pedidos
@app.post("/orders", status_code=201)
def create_order(body: OrderIn, user=Depends(user_dep)):
    entrega = body.fecha_entrega if body.fecha_entrega.tzinfo else body.fecha_entrega.replace(tzinfo=CL)
    now = datetime.now(timezone.utc)
    if entrega < now + timedelta(hours=24):
        raise HTTPException(422, "La entrega requiere al menos 24 horas de anticipación")
    if entrega > now + timedelta(days=60):
        raise HTTPException(422, "La fecha de entrega es demasiado lejana")
    order_id = str(uuid.uuid4())
    r = inv("POST", "/internal/reservations", json={
        "order_id": order_id,
        "items": [{"product_id": i.product_id, "cantidad": i.cantidad} for i in body.items]})
    if r.status_code == 409:
        raise HTTPException(409, r.json().get("detail"))
    if r.status_code >= 300:
        raise HTTPException(503, "Inventario no disponible; intenta nuevamente")
    lines = {l["product_id"]: l for l in r.json()["lines"]}
    try:
        for i in body.items:  # el mensaje personalizado solo aplica a productos personalizables
            if i.mensaje and not lines[i.product_id]["personalizable"]:
                raise HTTPException(422, f"El producto {i.product_id} no admite mensaje personalizado")
        total = D.compute_total(list(lines.values()))
        ts = int(time.time())
        with connect(DB) as c:
            with transaction(c):
                c.execute("INSERT INTO orders VALUES(?,?,?,?,?,?,?,NULL,?,?)",
                          (order_id, user.user_id, D.PENDIENTE_PAGO, total, body.direccion_entrega,
                           entrega.isoformat(), body.notas, ts, ts))
                for i in body.items:
                    l = lines[i.product_id]
                    c.execute("INSERT INTO order_items VALUES(?,?,?,?,?,?)",
                              (order_id, i.product_id, l["nombre"], l["precio_unitario"], i.cantidad, i.mensaje))
                _event(c, order_id, D.PENDIENTE_PAGO, user.user_id)
            out = _order(c, c.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone())
    except BaseException:
        inv("POST", f"/internal/reservations/{order_id}/release")  # compensación
        raise
    return out


@app.get("/orders")
def list_orders(estado: Optional[str] = None, limit: int = 20, offset: int = 0, user=Depends(user_dep)):
    limit, offset = page(limit, offset)
    where, args = [], []
    if not user.is_admin:
        where.append("cliente_id=?"); args.append(user.user_id)
    if estado:
        if estado not in D.TRANSITIONS:
            raise HTTPException(400, "Estado inválido")
        where.append("estado=?"); args.append(estado)
    sql = "SELECT * FROM orders" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY creado DESC LIMIT ? OFFSET ?"
    with connect(DB) as c:
        return [_order(c, r, admin=user.is_admin) for r in c.execute(sql, (*args, limit, offset)).fetchall()]


@app.get("/orders/{order_id}")
def get_order(order_id: str, user=Depends(user_dep)):
    with connect(DB) as c:
        return _order(c, _get_visible(c, order_id, user), admin=user.is_admin)


def _cancel(c, r, actor):
    with transaction(c):
        c.execute("UPDATE orders SET estado=?, actualizado=? WHERE id=?", (D.CANCELADO, int(time.time()), r["id"]))
        _event(c, r["id"], D.CANCELADO, actor)
    inv("POST", f"/internal/reservations/{r['id']}/release")  # devuelve el stock


@app.post("/orders/{order_id}/cancel")
def cancel_order(order_id: str, user=Depends(user_dep)):
    with connect(DB) as c:
        r = _get_visible(c, order_id, user)
        allowed = D.can_transition(r["estado"], D.CANCELADO) if user.is_admin else D.can_client_cancel(r["estado"])
        if not allowed:
            raise HTTPException(409, f"No se puede cancelar un pedido en estado {r['estado']}")
        _cancel(c, r, user.user_id)
        return _order(c, c.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone(), admin=user.is_admin)


@app.put("/orders/{order_id}/status")
def set_status(order_id: str, body: StatusIn, user=Depends(user_dep)):
    if not user.is_admin:
        raise HTTPException(403, "Operación denegada: requiere rol admin")
    if body.estado not in D.ADMIN_SETTABLE:
        raise HTTPException(422, "Estado no permitido para esta operación")
    with connect(DB) as c:
        r = _get_visible(c, order_id, user)
        if not D.can_transition(r["estado"], body.estado):
            raise HTTPException(409, f"Transición inválida: {r['estado']} -> {body.estado}")
        if body.estado == D.CANCELADO:
            _cancel(c, r, user.user_id)
        else:
            with transaction(c):
                c.execute("UPDATE orders SET estado=?, actualizado=? WHERE id=?", (body.estado, int(time.time()), order_id))
                _event(c, order_id, body.estado, user.user_id)
        return _order(c, c.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone(), admin=True)


# ------------------------------------------------------------------ internos (payments)
@app.get("/internal/orders/{order_id}")
def internal_get(order_id: str, caller=Depends(payments_dep)):
    with connect(DB) as c:
        r = c.execute("SELECT id,cliente_id,estado,total FROM orders WHERE id=?", (order_id,)).fetchone()
    if not r:
        raise HTTPException(404, "Pedido no encontrado")
    return dict(r)


@app.post("/internal/orders/{order_id}/mark-paid")
def mark_paid(order_id: str, body: PaidIn, caller=Depends(payments_dep)):
    with connect(DB) as c:
        r = c.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if not r:
            raise HTTPException(404, "Pedido no encontrado")
        if r["estado"] == D.PAGADO and r["payment_id"] == body.payment_id:
            return {"id": order_id, "estado": D.PAGADO, "idempotente": True}
        if r["estado"] != D.PENDIENTE_PAGO:
            raise HTTPException(409, f"El pedido está en estado {r['estado']}")
        if body.monto != r["total"]:
            raise HTTPException(409, "El monto no coincide con el total del pedido")
        rc = inv("POST", f"/internal/reservations/{order_id}/commit")
        if rc.status_code >= 300:
            raise HTTPException(503 if rc.status_code >= 500 else 409, "No se pudo confirmar la reserva de stock")
        with transaction(c):
            c.execute("UPDATE orders SET estado=?, payment_id=?, actualizado=? WHERE id=?",
                      (D.PAGADO, body.payment_id, int(time.time()), order_id))
            _event(c, order_id, D.PAGADO, "payments")
    return {"id": order_id, "estado": D.PAGADO}


# ------------------------------------------------------------------ expiración de impagos
def expire_unpaid() -> int:
    limit = int(time.time()) - TTL_MIN * 60
    with connect(DB) as c:
        rows = c.execute("SELECT * FROM orders WHERE estado=? AND creado<?", (D.PENDIENTE_PAGO, limit)).fetchall()
        for r in rows:
            try:
                _cancel(c, r, "system")
            except Exception:
                log.warning("orders no pudo expirar el pedido %s", r["id"])
    return len(rows)


async def _expire_loop():
    while True:
        await asyncio.sleep(60)
        try:
            await asyncio.to_thread(expire_unpaid)
        except Exception:
            log.warning("orders: fallo en expiración periódica")
