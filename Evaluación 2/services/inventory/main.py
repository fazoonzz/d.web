"""inventory: catálogo, stock y reservas. Única autoridad de precio y disponibilidad.

stock = unidades libres. Reservar descuenta; liberar devuelve; confirmar deja el descuento.
"""
import os
import time
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from common.svc import (admin_dependency, caller_dependency, connect, install_common,
                        page, transaction, user_dependency)

SERVICE = "inventory"
DB = os.getenv("INVENTORY_DB", "./data/inventory.db")
CATEGORIAS = ("Tortas Tradicionales", "Pastelería & Porciones", "Línea Sin Azúcar", "Postres & Cheesecakes")

public_dep = caller_dependency(SERVICE, {"gateway", "graphql"})  # lectura de catálogo
user_dep = user_dependency(SERVICE, allowed=("gateway",))        # administración (identidad requerida)
admin_dep = admin_dependency(user_dep)
orders_dep = caller_dependency(SERVICE, {"orders"})              # reservas: solo orders

app = FastAPI(title="Inventory Service (privado)")
install_common(app, SERVICE)

SEED = [
    ("Torta Chocolate Con Frutillas", "Bizcochuelo bañado en salsa de chocolate con frutillas frescas.", "Tortas Tradicionales", 18990, "Torta1.jpg", 1),
    ("Torta Piña", "Torta de piña con crema de leche y merengue.", "Tortas Tradicionales", 16500, "Torta2.JPG", 1),
    ("Pie de Limón Artesanal", "Masa crocante rellena de crema de limón y merengue.", "Postres & Cheesecakes", 12000, "Torta3.jpg", 0),
    ("Torta Selva Negra", "Bizcocho de cacao embebido en licor suave de cerezas, chantilly y chocolate.", "Tortas Tradicionales", 22990, "Torta4.jpg", 1),
    ("Torta Cuatro Leches", "Bizcocho húmedo con mezcla de cuatro leches y crema.", "Tortas Tradicionales", 17990, None, 1),
    ("Cheesecake Frambuesa", "Base de galleta, queso crema y coulis de frambuesa.", "Postres & Cheesecakes", 15990, None, 0),
]


class ProductIn(BaseModel):  # PUT reemplaza la representación completa
    nombre: str = Field(min_length=2, max_length=80)
    descripcion: str = Field(max_length=300)
    categoria: str
    precio: int = Field(ge=100, le=1_000_000)
    stock: int = Field(ge=0, le=10_000)
    personalizable: bool = False
    imagen: Optional[str] = Field(default=None, pattern=r"^[\w.\-]{1,100}$")


class StockIn(BaseModel):
    stock: int = Field(ge=0, le=10_000)


class ItemIn(BaseModel):
    product_id: int = Field(ge=1)
    cantidad: int = Field(ge=1, le=10)


class ReserveIn(BaseModel):
    order_id: str = Field(min_length=10, max_length=64)
    items: list[ItemIn] = Field(min_length=1, max_length=20)


with connect(DB) as _c:
    _c.executescript("""
    CREATE TABLE IF NOT EXISTS products(
      id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL, descripcion TEXT NOT NULL,
      categoria TEXT NOT NULL, precio INTEGER NOT NULL CHECK(precio>0),
      stock INTEGER NOT NULL CHECK(stock>=0), personalizable INTEGER NOT NULL DEFAULT 0,
      imagen TEXT, activo INTEGER NOT NULL DEFAULT 1, actualizado INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS reservations(
      order_id TEXT NOT NULL, product_id INTEGER NOT NULL REFERENCES products(id),
      nombre TEXT NOT NULL, precio_unitario INTEGER NOT NULL, personalizable INTEGER NOT NULL,
      cantidad INTEGER NOT NULL, estado TEXT NOT NULL CHECK(estado IN('RESERVADA','CONFIRMADA','LIBERADA')),
      creado INTEGER NOT NULL, PRIMARY KEY(order_id, product_id));
    """)
    if not _c.execute("SELECT 1 FROM products").fetchone():
        for n, d, cat, p, img, pers in SEED:
            _c.execute("INSERT INTO products(nombre,descripcion,categoria,precio,stock,personalizable,imagen,actualizado) "
                       "VALUES(?,?,?,?,10,?,?,?)", (n, d, cat, p, pers, img, int(time.time())))


def _pub(r, admin=False):
    d = {"id": r["id"], "nombre": r["nombre"], "descripcion": r["descripcion"], "categoria": r["categoria"],
         "precio": r["precio"], "personalizable": bool(r["personalizable"]),
         "disponible": r["stock"] > 0, "imagen": r["imagen"]}
    if admin:
        d["stock"] = r["stock"]
        d["activo"] = bool(r["activo"])
    return d


def _is_admin(roles: str) -> bool:
    return "admin" in [x.strip() for x in roles.split(",")]


# ------------------------------------------------------------------ catálogo público
@app.get("/products")
def list_products(available: Optional[bool] = None, categoria: Optional[str] = None, ids: Optional[str] = None,
                  limit: int = 50, offset: int = 0, caller=Depends(public_dep),
                  x_user_roles: str = Header(default="")):
    limit, offset = page(limit, offset)
    where, args = ["activo=1"], []
    if available:
        where.append("stock>0")
    if categoria:
        if categoria not in CATEGORIAS:
            raise HTTPException(400, "Categoría inválida")
        where.append("categoria=?"); args.append(categoria)
    if ids:
        try:
            idl = [int(x) for x in ids.split(",")][:50]
        except ValueError:
            raise HTTPException(400, "ids inválidos")
        where.append(f"id IN ({','.join('?' * len(idl))})"); args += idl
    with connect(DB) as c:
        rows = c.execute(f"SELECT * FROM products WHERE {' AND '.join(where)} ORDER BY id LIMIT ? OFFSET ?",
                         (*args, limit, offset)).fetchall()
    return [_pub(r, admin=_is_admin(x_user_roles)) for r in rows]


@app.get("/products/{product_id}")
def get_product(product_id: int, caller=Depends(public_dep), x_user_roles: str = Header(default="")):
    with connect(DB) as c:
        r = c.execute("SELECT * FROM products WHERE id=? AND activo=1", (product_id,)).fetchone()
    if not r:
        raise HTTPException(404, "Producto no encontrado")
    return _pub(r, admin=_is_admin(x_user_roles))


# ------------------------------------------------------------------ administración
def _check_cat(cat):
    if cat not in CATEGORIAS:
        raise HTTPException(422, "Categoría inválida")


@app.post("/products", status_code=201)
def create_product(body: ProductIn, user=Depends(admin_dep)):
    _check_cat(body.categoria)
    with connect(DB) as c:
        cur = c.execute("INSERT INTO products(nombre,descripcion,categoria,precio,stock,personalizable,imagen,actualizado)"
                        " VALUES(?,?,?,?,?,?,?,?)",
                        (body.nombre, body.descripcion, body.categoria, body.precio, body.stock,
                         int(body.personalizable), body.imagen, int(time.time())))
        r = c.execute("SELECT * FROM products WHERE id=?", (cur.lastrowid,)).fetchone()
    return _pub(r, admin=True)


@app.put("/products/{product_id}")
def replace_product(product_id: int, body: ProductIn, user=Depends(admin_dep)):
    _check_cat(body.categoria)
    with connect(DB) as c:
        n = c.execute("UPDATE products SET nombre=?,descripcion=?,categoria=?,precio=?,stock=?,personalizable=?,"
                      "imagen=?,actualizado=? WHERE id=? AND activo=1",
                      (body.nombre, body.descripcion, body.categoria, body.precio, body.stock,
                       int(body.personalizable), body.imagen, int(time.time()), product_id)).rowcount
        if not n:
            raise HTTPException(404, "Producto no encontrado")
        r = c.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    return _pub(r, admin=True)


@app.put("/products/{product_id}/stock")
def set_stock(product_id: int, body: StockIn, user=Depends(admin_dep)):
    with connect(DB) as c:
        n = c.execute("UPDATE products SET stock=?, actualizado=? WHERE id=? AND activo=1",
                      (body.stock, int(time.time()), product_id)).rowcount
        if not n:
            raise HTTPException(404, "Producto no encontrado")
        r = c.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    return _pub(r, admin=True)


@app.delete("/products/{product_id}")
def delete_product(product_id: int, user=Depends(admin_dep)):
    # Baja lógica: los pedidos históricos conservan nombre y precio vía reservations/orders.
    with connect(DB) as c:
        n = c.execute("UPDATE products SET activo=0, actualizado=? WHERE id=? AND activo=1",
                      (int(time.time()), product_id)).rowcount
    if not n:
        raise HTTPException(404, "Producto no encontrado")
    return {"message": "Producto dado de baja", "id": product_id}


# ------------------------------------------------------------------ reservas (solo orders)
def _lines(rows):
    return [{"product_id": r["product_id"], "nombre": r["nombre"], "precio_unitario": r["precio_unitario"],
             "cantidad": r["cantidad"], "personalizable": bool(r["personalizable"])} for r in rows]


@app.post("/internal/reservations")
def reserve(body: ReserveIn, caller=Depends(orders_dep)):
    with connect(DB) as c:
        with transaction(c):
            prev = c.execute("SELECT * FROM reservations WHERE order_id=?", (body.order_id,)).fetchall()
            if prev:  # idempotente: reintentos de orders no duplican descuentos
                return {"order_id": body.order_id, "lines": _lines(prev)}
            lines, faltantes = [], []
            ids = [i.product_id for i in body.items]
            if len(set(ids)) != len(ids):
                raise HTTPException(422, "Producto repetido en el pedido")
            for it in body.items:
                p = c.execute("SELECT * FROM products WHERE id=? AND activo=1", (it.product_id,)).fetchone()
                if not p:
                    faltantes.append({"product_id": it.product_id, "motivo": "no_disponible"})
                elif p["stock"] < it.cantidad:
                    faltantes.append({"product_id": it.product_id, "motivo": "stock_insuficiente",
                                      "disponible": p["stock"]})
                else:
                    lines.append((p, it.cantidad))
            if faltantes:
                raise HTTPException(409, {"mensaje": "Stock insuficiente", "items": faltantes})
            now = int(time.time())
            for p, q in lines:
                c.execute("UPDATE products SET stock=stock-? WHERE id=?", (q, p["id"]))
                c.execute("INSERT INTO reservations VALUES(?,?,?,?,?,?,'RESERVADA',?)",
                          (body.order_id, p["id"], p["nombre"], p["precio"], p["personalizable"], q, now))
            out = c.execute("SELECT * FROM reservations WHERE order_id=?", (body.order_id,)).fetchall()
    return {"order_id": body.order_id, "lines": _lines(out)}


@app.post("/internal/reservations/{order_id}/release")
def release(order_id: str, caller=Depends(orders_dep)):
    with connect(DB) as c:
        with transaction(c):
            rows = c.execute("SELECT * FROM reservations WHERE order_id=? AND estado!='LIBERADA'", (order_id,)).fetchall()
            for r in rows:
                c.execute("UPDATE products SET stock=stock+? WHERE id=?", (r["cantidad"], r["product_id"]))
            c.execute("UPDATE reservations SET estado='LIBERADA' WHERE order_id=?", (order_id,))
    return {"order_id": order_id, "liberadas": len(rows)}


@app.post("/internal/reservations/{order_id}/commit")
def commit(order_id: str, caller=Depends(orders_dep)):
    with connect(DB) as c:
        n = c.execute("UPDATE reservations SET estado='CONFIRMADA' WHERE order_id=? AND estado='RESERVADA'",
                      (order_id,)).rowcount
        if not n and not c.execute("SELECT 1 FROM reservations WHERE order_id=? AND estado='CONFIRMADA'",
                                   (order_id,)).fetchone():
            raise HTTPException(409, "La reserva no existe o ya fue liberada")
    return {"order_id": order_id, "estado": "CONFIRMADA"}
