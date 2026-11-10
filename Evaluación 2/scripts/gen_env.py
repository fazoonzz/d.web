"""Genera .env con valores aleatorios (no se versiona). Uso: python scripts/gen_env.py"""
import os
import secrets
import sys

if os.path.exists(".env") and "--force" not in sys.argv:
    sys.exit(".env ya existe (usa --force para regenerarlo)")

lines = ["# Generado por scripts/gen_env.py. NO subir a Git.",
         f"VAULT_ROOT_TOKEN={secrets.token_urlsafe(24)}"]
for s in ("gateway", "auth", "clients", "inventory", "orders", "payments", "graphql"):
    lines.append(f"VAULT_TOKEN_{s.upper()}={secrets.token_urlsafe(24)}")
lines += [
    f"PAYMENTS_WEBHOOK_SECRET={secrets.token_urlsafe(32)}",
    "SEED_ADMIN_EMAIL=admin@dulcetentacion.test",
    f"SEED_ADMIN_PASSWORD={secrets.token_urlsafe(12)}",
    "SEED_CLIENT_EMAIL=cliente@dulcetentacion.test",
    f"SEED_CLIENT_PASSWORD={secrets.token_urlsafe(12)}",
    "CORS_ORIGINS=http://localhost:8080,http://127.0.0.1:8080",
    "COOKIE_SECURE=false",
    "PAYMENT_SANDBOX=true",
]
open(".env", "w").write("\n".join(lines) + "\n")
print(".env creado. Credenciales semilla de prueba: ver SEED_* dentro del archivo.")
