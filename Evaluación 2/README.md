# Dulce Tentación — Backend seguro (Evaluación 2)

Caso: **Pastelería Dulce Tentación — tortas personalizadas y pasteles**.

## Arquitectura

```
Cliente (navegador / curl / pruebas)
     │
     └─ cookie HttpOnly ─► API Gateway :8000  (único backend público)
                              │  valida sesión · roles · lista blanca de rutas · rate limit · reconstruye identidad
        red privada (internal) ▼
        ┌── auth :8100 ──► clients      credenciales / sesiones
        ├── clients :9001               perfil y datos personales
        ├── inventory :9002             catálogo, stock, reservas (autoridad de precio)
        ├── orders :9003 ──► inventory  pedidos y estados (autoridad del estado)
        ├── payments :9004 ──► orders   pagos + webhook firmado (único que marca PAGADO)
        ├── graphql :8090 ──► orders, inventory, clients   agregación (privado)
        └── vault :8200                 secretos; un token y una política por servicio
```

* Solo 8000 (gateway) se publica en el host, y solo en 127.0.0.1. Los demás servicios están en una red Docker internal.
* Persistencia: SQLite por servicio (volumen propio). Cada servicio modifica únicamente sus datos.
* Tecnología: FastAPI + httpx + Vault + Node (GraphQL), como en clases.

## Arranque

```bash
python scripts/gen_env.py          # crea .env con secretos aleatorios (no se versiona)
docker compose up --build          # primera vez: construye imágenes
# API: http://localhost:8000/api/v1
```
Credenciales de prueba: ver `SEED_ADMIN_*` y `SEED_CLIENT_*` en `.env`. Detener: `docker compose down` (`-v` borra datos).
Vault corre en modo **dev** (en memoria): `vault-init` recarga secretos en cada arranque.

## Pruebas

```bash
pip install -r requirements.txt
set -a; . ./.env; set +a; pytest tests/test_security_e2e.py -v 
```

## Rutas externas (gateway, prefijo `/api/v1`) — lista blanca

 Verbo - Ruta - Acceso - Destino interno 

 POST - /auth/register ; /auth/login - anónimo (10/min por IP) - auth 
 POST - /auth/logout ; GET /auth/me - sesión - auth 
 GET - /products ; /products/{id} - anónimo (admin ve stock) - inventory 
 POST/PUT/DELETE - /products ; /products/{id} ; /products/{id}/stock - **admin** - inventory 
 GET/PUT - /clients/me - cliente - clients 
 GET - /clients ; /clients/{id} - **admin** - clients 
 POST/GET - /orders ; /orders/{id} - cliente (solo propios) / admin - orders 
 POST - /orders/{id}/cancel - dueño (solo PENDIENTE_PAGO) / admin - orders 
 PUT - /orders/{id}/status - **admin** - orders 
 POST/GET - /payments ; /payments/{id} - dueño del pedido - payments 
 POST - /payments/{id}/sandbox-resolve - dueño, solo si `PAYMENT_SANDBOX=true` - payments 
 POST - /payments/webhook - anónimo en red, **firma HMAC** obligatoria - payments 
 POST - /graphql - sesión; autorización por recurso y campo - graphql 

Todo lo que no figura aquí responde 404/405. No existe ruta pública hacia `/internal/*`.

## Secretos (referencias simbólicas; valores solo en Vault)

Regla: **una clave distinta por tramo**. El llamador guarda `to_<destino>`; el destino guarda `from_<llamador>`.

  Referencia (Vault) | Emisor | Consumidor | Finalidad |

  secret/gateway → `to_auth/clients/inventory/orders/payments/graphql` - init_vault - gateway - autenticarse ante cada servicio 
  secret/auth → `from_gateway`, `to_clients` - init_vault - auth - recibir del gateway / crear perfil 
  secret/clients → `from_gateway`, `from_graphql`, `from_auth` - init_vault - clients - verificar llamadores 
  secret/inventory → `from_gateway`, `from_graphql`, `from_orders` - init_vault - inventory - verificar llamadores 
  secret/orders → `from_gateway`, `from_graphql`, `from_payments`, `to_inventory` - init_vault - orders - verificar / reservar stock 
  secret/payments → `from_gateway`, `to_orders`, `webhook_secret` - init_vault - payments - verificar / confirmar pago / firma del proveedor 
  secret/graphql → `from_gateway`, `to_orders`, `to_inventory`, `to_clients` - init_vault - graphql - agregación 

Cada servicio tiene su propio token de Vault con política de **solo lectura sobre su ruta**. Rotación: volver a ejecutar
`vault-init` (genera claves nuevas) y reiniciar servicios. Revocación: `vault token revoke` del servicio afectado.
Si Vault no responde, los servicios siguen con la copia en memoria (5 min) y fallan cerrados si no tienen ninguna.

## Datos y reglas clave

* Contraseñas: **scrypt con sal** (stdlib). Tokens de sesión: aleatorios, guardados como SHA-256, 15 min, cookie HttpOnly + SameSite=Lax.
* Precio/total/estado nunca vienen del navegador: orders pide los precios a inventory y calcula el total.
* Stock: reserva atómica al crear el pedido; se libera al cancelar o a los 30 min sin pago; se confirma al pagar.
* Pago: monto tomado del pedido; webhook con HMAC + marca de tiempo (±5 min) + `event_id` idempotente; orders valida monto y estado.
* Pedido cancelado = estado `CANCELADO` + historial (`order_events`); productos = baja lógica. No se borran registros de negocio.
* No se almacena RUN (no es necesario para el negocio). Logs: método, ruta, estado, tiempo y `X-Correlation-Id`; sin cuerpos ni cabeceras.

## Pendiente / límites conocidos

* Formulario de **Contacto** (comentarios y rating) todavía no tiene servicio: es una brecha por declarar/resolver.
* El proveedor de pagos es un **adaptador sandbox** (mismo contrato firmado); no hay pasarela real.
* gRPC y analítica: se espera un ADR de "no aplica" fundamentado (volumen bajo; reportes simples vía GraphQL/REST).
* Rate limit en memoria (una instancia de gateway); Vault en modo dev; SQLite (no apta para múltiples réplicas).
