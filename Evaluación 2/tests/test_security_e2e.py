"""Pruebas de seguridad y flujo contra el stack real (docker compose up).

Uso:  set -a; . ./.env; set +a; pytest tests/test_security_e2e.py -v
Cada prueba documenta: entrada, identidad, resultado esperado y componente que lo verifica.
"""
import json
import os
import time
import uuid

import pytest
import requests

from common.security import sign_webhook

GW = os.getenv("GATEWAY_URL", "http://localhost:8000") + "/api/v1"
ADMIN = (os.getenv("SEED_ADMIN_EMAIL"), os.getenv("SEED_ADMIN_PASSWORD"))
WEBHOOK_SECRET = os.getenv("PAYMENTS_WEBHOOK_SECRET")


def entrega():
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() + 3 * 86400))


def session(email, password):
    s = requests.Session()
    r = s.post(f"{GW}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return s


def new_client():
    email, pw = f"t{uuid.uuid4().hex[:10]}@prueba.test", "ClaveDePrueba#2026"
    r = requests.post(f"{GW}/auth/register", json={"email": email, "password": pw, "nombre": "Cliente Prueba"})
    assert r.status_code == 201, r.text
    return session(email, pw)


@pytest.fixture(scope="module")
def admin():
    assert all(ADMIN), "Carga el .env (SEED_ADMIN_*)"
    return session(*ADMIN)


@pytest.fixture(scope="module")
def ana():
    return new_client()


@pytest.fixture(scope="module")
def beto():
    return new_client()


def make_order(s, product_id=1, cantidad=1, extra=None):
    body = {"items": [{"product_id": product_id, "cantidad": cantidad}],
            "direccion_entrega": "Av. Pajaritos 1234, Maipú", "fecha_entrega": entrega()}
    body.update(extra or {})
    return s.post(f"{GW}/orders", json=body)


# 1. Acceso anónimo al catálogo -> 200 solo con campos públicos (inventory).
def test_catalogo_anonimo_solo_campos_publicos():
    r = requests.get(f"{GW}/products?available=true")
    assert r.status_code == 200 and r.json()
    assert "stock" not in r.json()[0] and "activo" not in r.json()[0]


# 2. Operación protegida sin sesión -> 401 (gateway).
@pytest.mark.parametrize("method,path", [("GET", "/orders"), ("POST", "/orders"), ("GET", "/clients/me"),
                                         ("POST", "/payments"), ("POST", "/graphql")])
def test_sin_sesion_401(method, path):
    assert requests.request(method, GW + path, json={}).status_code == 401


# 3. Administración desde rol cliente -> 403 (gateway y, de nuevo, inventory).
def test_cliente_no_administra_catalogo(ana):
    assert ana.delete(f"{GW}/products/1").status_code == 403
    assert ana.put(f"{GW}/products/1/stock", json={"stock": 999}).status_code == 403
    assert ana.get(f"{GW}/clients").status_code == 403


# 4. Pedido ajeno -> 404 sin datos (orders verifica propiedad).
def test_pedido_ajeno_no_visible(ana, beto, admin):
    oid = make_order(ana).json()["id"]
    assert beto.get(f"{GW}/orders/{oid}").status_code == 404
    assert beto.post(f"{GW}/orders/{oid}/cancel").status_code == 404
    assert ana.get(f"{GW}/orders/{oid}").status_code == 200
    assert admin.get(f"{GW}/orders/{oid}").status_code == 200
    assert oid not in [o["id"] for o in beto.get(f"{GW}/orders").json()]


# 5. Acceso directo al backend sin pasar por el gateway -> inalcanzable desde el host.
@pytest.mark.parametrize("port", [8100, 9001, 9002, 9003, 9004, 8090, 8200])
def test_servicios_privados_no_publicados(port):
    with pytest.raises(requests.exceptions.ConnectionError):
        requests.get(f"http://localhost:{port}/health", timeout=2)


# 6. Rutas internas no se publican y el navegador no puede inyectar identidad.
def test_rutas_internas_no_expuestas(ana):
    assert ana.post(f"{GW}/internal/orders/x/mark-paid", json={}).status_code == 404
    assert ana.get(f"{GW}/products/1/../../internal/clients").status_code in (404, 405)


def test_cabeceras_de_identidad_del_navegador_se_descartan(ana):
    r = ana.get(f"{GW}/orders", headers={"X-User-Id": "otro", "X-User-Roles": "admin", "X-Service-Name": "gateway"})
    assert r.status_code == 200
    assert ana.get(f"{GW}/clients", headers={"X-User-Roles": "admin"}).status_code == 403


# 7. Precio/total alterados desde el frontend -> se ignoran; el total lo calcula el servidor.
def test_total_lo_calcula_el_servidor(ana):
    cat = {p["id"]: p for p in requests.get(f"{GW}/products").json()}
    r = make_order(ana, 1, 2, extra={"total": 1, "precio": 1, "estado": "PAGADO"})
    assert r.status_code == 201
    o = r.json()
    assert o["estado"] == "PENDIENTE_PAGO" and o["total"] == cat[1]["precio"] * 2


def test_stock_insuficiente_409_y_cantidad_invalida_422(ana, admin):
    assert make_order(ana, 1, 11).status_code == 422             # cantidad > 10: validación del servidor
    assert admin.put(f"{GW}/products/3/stock", json={"stock": 1}).status_code == 200
    r = make_order(ana, 3, 2)
    assert r.status_code == 409 and r.json()["detail"]["items"][0]["motivo"] == "stock_insuficiente"
    assert admin.put(f"{GW}/products/3/stock", json={"stock": 10}).status_code == 200


# 8. Confirmar pago con datos alterados -> rechazado.
def test_webhook_sin_firma_o_falsificado_rechazado():
    body = json.dumps({"event_id": "x", "payment_id": "y", "monto": 1, "tipo": "payment.approved"})
    assert requests.post(f"{GW}/payments/webhook", data=body, headers={"Content-Type": "application/json"}).status_code == 401
    h = {"Content-Type": "application/json", "X-Timestamp": str(int(time.time())), "X-Signature": "00" * 32}
    assert requests.post(f"{GW}/payments/webhook", data=body, headers=h).status_code == 401


def test_cliente_no_puede_marcar_pagado_por_otra_via(ana, admin):
    oid = make_order(ana).json()["id"]
    assert admin.put(f"{GW}/orders/{oid}/status", json={"estado": "PAGADO"}).status_code == 422
    assert ana.put(f"{GW}/orders/{oid}/status", json={"estado": "PAGADO"}).status_code == 403


def test_pago_completo_idempotente_y_monto_alterado(ana, admin):
    if not WEBHOOK_SECRET:
        pytest.skip("Define PAYMENTS_WEBHOOK_SECRET (del .env) para probar el webhook firmado")
    oid = make_order(ana).json()["id"]
    pay = ana.post(f"{GW}/payments", json={"order_id": oid}).json()

    def send(ev, secret=WEBHOOK_SECRET):
        raw = json.dumps(ev).encode()
        ts = str(int(time.time()))
        return requests.post(f"{GW}/payments/webhook", data=raw, headers={
            "Content-Type": "application/json", "X-Timestamp": ts, "X-Signature": sign_webhook(secret, ts, raw)})

    ev = {"event_id": uuid.uuid4().hex, "payment_id": pay["id"], "monto": pay["monto"], "tipo": "payment.approved"}
    assert send({**ev, "monto": 1}).status_code == 409                 # monto alterado, firma válida
    assert ana.get(f"{GW}/orders/{oid}").json()["estado"] == "PENDIENTE_PAGO"
    assert send(ev).status_code == 200
    assert send(ev).json().get("duplicado") is True                    # mismo event_id: no se procesa dos veces
    assert ana.get(f"{GW}/orders/{oid}").json()["estado"] == "PAGADO"
    assert ana.post(f"{GW}/orders/{oid}/cancel").status_code == 409    # cliente no cancela pedido pagado


def test_pago_de_pedido_ajeno_denegado(ana, beto):
    oid = make_order(ana).json()["id"]
    assert beto.post(f"{GW}/payments", json={"order_id": oid}).status_code == 404


# 9. Cancelación devuelve stock.
def test_cancelar_devuelve_stock(ana, admin):
    antes = [p for p in admin.get(f"{GW}/products").json() if p["id"] == 2][0]["stock"]
    oid = make_order(ana, 2, 2).json()["id"]
    mid = [p for p in admin.get(f"{GW}/products").json() if p["id"] == 2][0]["stock"]
    assert mid == antes - 2
    assert ana.post(f"{GW}/orders/{oid}/cancel").status_code == 200
    assert [p for p in admin.get(f"{GW}/products").json() if p["id"] == 2][0]["stock"] == antes


# 10. GraphQL: identidad, propiedad, campos por rol, límites.
GQL_PEDIDO = "query($id: ID!){ resumenPedido(id:$id){ id estado total items{ nombre cantidad producto{ nombre precio } } } }"


def gql(s, query, variables=None):
    return s.post(f"{GW}/graphql", json={"query": query, "variables": variables or {}})


def test_graphql_agrega_orders_e_inventory(ana):
    oid = make_order(ana).json()["id"]
    d = gql(ana, GQL_PEDIDO, {"id": oid}).json()["data"]["resumenPedido"]
    assert d["id"] == oid and d["items"][0]["producto"]["nombre"]       # dato de inventory dentro del pedido de orders


def test_graphql_pedido_ajeno_es_null(ana, beto):
    oid = make_order(ana).json()["id"]
    assert gql(beto, GQL_PEDIDO, {"id": oid}).json()["data"]["resumenPedido"] is None


def test_graphql_campo_cliente_solo_admin(ana, admin):
    oid = make_order(ana).json()["id"]
    q = "query($id: ID!){ resumenPedido(id:$id){ id cliente{ email } } }"
    r = gql(ana, q, {"id": oid}).json()
    assert r["data"]["resumenPedido"]["cliente"] is None and r["errors"]
    r = gql(admin, q, {"id": oid}).json()
    assert r["data"]["resumenPedido"]["cliente"]["email"]


def test_graphql_limites_y_mutaciones(ana):
    assert gql(ana, "mutation{ x }").status_code == 400                       # no hay mutaciones en el schema
    muchos = "query{ " + " ".join(f"a{i}: misPedidos{{id}}" for i in range(70)) + " }"
    assert gql(ana, muchos).status_code == 400                                # más de 60 campos: costo excedido
    assert gql(ana, "query{ misPedidos(limit: 9999){ id } }").status_code == 200   # el límite se acota a 20
    assert gql(ana, "x" * 5000).status_code == 400                            # consulta demasiado larga


# 11. Registro y sesión.
def test_login_invalido_no_distingue_usuario_ni_clave():
    a = requests.post(f"{GW}/auth/login", json={"email": "noexiste@x.test", "password": "xxxxxxxxxxxx"})
    b = requests.post(f"{GW}/auth/login", json={"email": ADMIN[0], "password": "incorrecta-123"})
    assert a.status_code == b.status_code == 401 and a.json() == b.json()


def test_token_no_se_entrega_al_javascript_y_cookie_httponly():
    r = requests.post(f"{GW}/auth/login", json={"email": ADMIN[0], "password": ADMIN[1]})
    assert "access_token" not in r.text
    assert "httponly" in r.headers["set-cookie"].lower()


def test_logout_invalida_sesion():
    s = session(*ADMIN)
    assert s.get(f"{GW}/auth/me").status_code == 200
    token = s.cookies.get("session_token")
    s.post(f"{GW}/auth/logout")
    assert requests.get(f"{GW}/auth/me", cookies={"session_token": token}).status_code == 401


def test_registro_valida_clave_corta_y_correo_duplicado():
    assert requests.post(f"{GW}/auth/register", json={"email": "a@b.cl", "password": "corta", "nombre": "Ana"}).status_code == 422
    email = f"d{uuid.uuid4().hex[:8]}@prueba.test"
    ok = {"email": email, "password": "ClaveDePrueba#2026", "nombre": "Dup"}
    assert requests.post(f"{GW}/auth/register", json=ok).status_code == 201
    assert requests.post(f"{GW}/auth/register", json=ok).status_code == 409


def test_perfil_cliente_y_datos_minimos(ana):
    r = ana.put(f"{GW}/clients/me", json={"nombre": "Ana Pérez", "telefono": "+56 9 1234 5678", "direccion": "Los Pinos 123, Maipú"})
    assert r.status_code == 200 and "password" not in json.dumps(r.json()).lower()
    assert ana.get(f"{GW}/clients/me").json()["nombre"] == "Ana Pérez"


# 12. Administración legítima: ciclo del pedido y baja lógica.
def test_admin_ciclo_de_vida_del_pedido(ana, admin):
    if not WEBHOOK_SECRET:
        pytest.skip("Requiere PAYMENTS_WEBHOOK_SECRET")
    oid = make_order(ana).json()["id"]
    pay = ana.post(f"{GW}/payments", json={"order_id": oid}).json()
    assert ana.post(f"{GW}/payments/{pay['id']}/sandbox-resolve", json={"resultado": "approved"}).status_code in (200, 404)
    if ana.get(f"{GW}/orders/{oid}").json()["estado"] != "PAGADO":
        pytest.skip("Sandbox desactivado (PAYMENT_SANDBOX=false)")
    assert admin.put(f"{GW}/orders/{oid}/status", json={"estado": "ENTREGADO"}).status_code == 409   # salto inválido
    for e in ("EN_PREPARACION", "LISTO", "EN_REPARTO", "ENTREGADO"):
        assert admin.put(f"{GW}/orders/{oid}/status", json={"estado": e}).status_code == 200
    h = ana.get(f"{GW}/orders/{oid}").json()["historial"]
    assert [x["estado"] for x in h][-1] == "ENTREGADO" and len(h) >= 6    # historial conservado


def test_baja_logica_de_producto(admin):
    nuevo = admin.post(f"{GW}/products", json={"nombre": "Producto Temporal", "descripcion": "x", "categoria": "Tortas Tradicionales",
                                              "precio": 1000, "stock": 1}).json()
    assert admin.delete(f"{GW}/products/{nuevo['id']}").status_code == 200
    assert requests.get(f"{GW}/products/{nuevo['id']}").status_code == 404
