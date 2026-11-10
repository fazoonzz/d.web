"""Tabla explícita de rutas del gateway. Lo que no está aquí NO se publica (deny by default).

access: anon | user | admin.   limit: cubo de límite de solicitudes.
La autorización fina (propiedad del recurso, estado del pedido) la repite cada servicio.
"""
import re
from dataclasses import dataclass

SEG = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


@dataclass(frozen=True)
class Route:
    method: str
    path: str            # ruta externa, relativa a /api/v1
    service: str
    target: str          # ruta interna (puede usar los mismos {parametros})
    access: str = "user"
    limit: str = "default"
    extra_headers: tuple = ()   # cabeceras del cliente que se reenvían tal cual (p. ej. firma del webhook)


ROUTES: list[Route] = [
    # --- inventory (catálogo público, administración restringida)
    Route("GET", "/products", "inventory", "/products", "anon"),
    Route("GET", "/products/{id}", "inventory", "/products/{id}", "anon"),
    Route("POST", "/products", "inventory", "/products", "admin"),
    Route("PUT", "/products/{id}/stock", "inventory", "/products/{id}/stock", "admin"),
    Route("PUT", "/products/{id}", "inventory", "/products/{id}", "admin"),
    Route("DELETE", "/products/{id}", "inventory", "/products/{id}", "admin"),
    # --- clients
    Route("GET", "/clients/me", "clients", "/clients/me"),
    Route("PUT", "/clients/me", "clients", "/clients/me"),
    Route("GET", "/clients", "clients", "/clients", "admin"),
    Route("GET", "/clients/{id}", "clients", "/clients/{id}", "admin"),
    # --- orders
    Route("POST", "/orders", "orders", "/orders"),
    Route("GET", "/orders", "orders", "/orders"),
    Route("GET", "/orders/{id}", "orders", "/orders/{id}"),
    Route("POST", "/orders/{id}/cancel", "orders", "/orders/{id}/cancel"),
    Route("PUT", "/orders/{id}/status", "orders", "/orders/{id}/status", "admin"),
    # --- payments
    Route("POST", "/payments", "payments", "/payments"),
    Route("GET", "/payments/{id}", "payments", "/payments/{id}"),
    Route("POST", "/payments/{id}/sandbox-resolve", "payments", "/payments/{id}/sandbox-resolve"),
    Route("POST", "/payments/webhook", "payments", "/payments/webhook", "anon", "webhook",
          ("x-signature", "x-timestamp")),   # anónimo en red; autenticado por firma HMAC en payments
    # --- agregaciones
    Route("POST", "/graphql", "graphql", "/graphql"),
]


def match(method: str, path: str):
    """Devuelve (Route, params) o None. Los segmentos {x} solo admiten [A-Za-z0-9_-]{1,64}."""
    segs = [s for s in path.strip("/").split("/")]
    for r in ROUTES:
        if r.method != method:
            continue
        rs = r.path.strip("/").split("/")
        if len(rs) != len(segs):
            continue
        params, ok = {}, True
        for a, b in zip(rs, segs):
            if a.startswith("{"):
                if not SEG.match(b):
                    ok = False
                    break
                params[a[1:-1]] = b
            elif a != b:
                ok = False
                break
        if ok:
            return r, params
    return None


def known_path(path: str) -> bool:
    """¿Existe la ruta con algún otro verbo? (para responder 405 en lugar de 404)."""
    return any(match(m, path) for m in {r.method for r in ROUTES})
