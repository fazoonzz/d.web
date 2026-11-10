"""Pruebas unitarias de la lógica pura (no requieren servicios levantados)."""
import json
import time

from common.security import (RateLimiter, hash_password, sign_webhook, verify_password, verify_webhook)
from gateway.routes import ROUTES, known_path, match
from services.orders import domain as D


# ---- contraseñas
def test_hash_con_sal_y_verificacion():
    h1, h2 = hash_password("ClaveSegura123"), hash_password("ClaveSegura123")
    assert h1 != h2                      # sal distinta en cada hash
    assert h1.startswith("scrypt$") and "ClaveSegura123" not in h1
    assert verify_password("ClaveSegura123", h1)
    assert not verify_password("otra", h1)
    assert not verify_password("x", "formato-invalido")


# ---- webhook firmado
def test_webhook_firma_ventana_y_alteracion():
    body = json.dumps({"event_id": "e1", "monto": 18990}).encode()
    ts = str(int(time.time()))
    sig = sign_webhook("secreto", ts, body)
    assert verify_webhook("secreto", ts, body, sig)
    assert not verify_webhook("otro", ts, body, sig)                                   # secreto distinto
    assert not verify_webhook("secreto", ts, body.replace(b"18990", b"1"), sig)        # monto alterado
    assert not verify_webhook("secreto", str(int(ts) - 1000), body, sig, now=int(ts))  # fuera de ventana
    assert not verify_webhook("secreto", "abc", body, sig)
    assert not verify_webhook("secreto", ts, body, "")


# ---- límite de solicitudes
def test_rate_limiter_ventana_deslizante():
    rl = RateLimiter()
    assert all(rl.allow("ip:auth", 3, 60, now=t) for t in (0, 1, 2))
    assert not rl.allow("ip:auth", 3, 60, now=3)
    assert rl.allow("otra-ip:auth", 3, 60, now=3)       # independiente por clave
    assert rl.allow("ip:auth", 3, 60, now=61)           # la ventana se libera


# ---- tabla de rutas (deny by default)
def test_rutas_publicas_y_privadas():
    r, p = match("GET", "/products/5")
    assert r.access == "anon" and p == {"id": "5"}
    assert match("PUT", "/products/5/stock")[0].access == "admin"
    assert match("DELETE", "/products/5")[0].access == "admin"
    assert match("GET", "/clients/me")[0].target == "/clients/me"      # 'me' antes que {id}
    assert match("POST", "/payments/webhook")[0].access == "anon"


def test_rutas_internas_no_publicadas():
    for path in ("/internal/orders/1/mark-paid", "/internal/reservations", "/internal/clients"):
        for verb in ("GET", "POST", "PUT", "DELETE"):
            assert match(verb, path) is None
    assert all("internal" not in r.path for r in ROUTES)


def test_verbo_no_permitido_y_parametros_invalidos():
    assert match("DELETE", "/orders/1") is None and known_path("/orders/1")     # existe con otro verbo -> 405
    assert match("GET", "/nada") is None and not known_path("/nada")            # 404
    assert match("GET", "/orders/../internal") is None
    assert match("GET", "/orders/a%2Fb") is None
    assert match("GET", "/orders/" + "x" * 65) is None


# ---- ciclo de vida del pedido
def test_transiciones_validas_e_invalidas():
    assert D.can_transition(D.PENDIENTE_PAGO, D.PAGADO)
    assert D.can_transition(D.PAGADO, D.EN_PREPARACION)
    assert not D.can_transition(D.PENDIENTE_PAGO, D.ENTREGADO)       # no se salta estados
    assert not D.can_transition(D.EN_PREPARACION, D.CANCELADO)       # torta ya en preparación
    assert not D.can_transition(D.ENTREGADO, D.CANCELADO)
    assert not D.can_transition(D.CANCELADO, D.PAGADO)


def test_pagado_no_lo_fija_un_admin_y_cliente_solo_cancela_impagos():
    assert D.PAGADO not in D.ADMIN_SETTABLE
    assert D.can_client_cancel(D.PENDIENTE_PAGO)
    assert not D.can_client_cancel(D.PAGADO)


def test_total_calculado_en_servidor():
    lines = [{"precio_unitario": 18990, "cantidad": 2}, {"precio_unitario": 12000, "cantidad": 1}]
    assert D.compute_total(lines) == 49980
