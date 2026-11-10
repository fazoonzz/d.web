"""Reglas puras del ciclo de vida del pedido (sin framework, probables en aislado)."""

PENDIENTE_PAGO, PAGADO, EN_PREPARACION, LISTO, EN_REPARTO, ENTREGADO, CANCELADO = (
    "PENDIENTE_PAGO", "PAGADO", "EN_PREPARACION", "LISTO", "EN_REPARTO", "ENTREGADO", "CANCELADO")

TRANSITIONS = {
    PENDIENTE_PAGO: {PAGADO, CANCELADO},
    PAGADO: {EN_PREPARACION, CANCELADO},
    EN_PREPARACION: {LISTO},          # una torta ya en preparación no se cancela
    LISTO: {EN_REPARTO},
    EN_REPARTO: {ENTREGADO},
    ENTREGADO: set(),
    CANCELADO: set(),
}

# El estado PAGADO solo lo fija el servicio payments (nunca el navegador ni un admin a mano).
ADMIN_SETTABLE = {EN_PREPARACION, LISTO, EN_REPARTO, ENTREGADO, CANCELADO}


def can_transition(actual: str, nuevo: str) -> bool:
    return nuevo in TRANSITIONS.get(actual, set())


def can_client_cancel(estado: str) -> bool:
    return estado == PENDIENTE_PAGO


def compute_total(lines: list[dict]) -> int:
    """Total calculado en el servidor a partir de precios del inventario."""
    return sum(l["precio_unitario"] * l["cantidad"] for l in lines)
