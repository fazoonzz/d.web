"""Carga los secretos en Vault con una política y un token de lectura POR SERVICIO.

Cada tramo de comunicación tiene su propia clave:
  llamador guarda  to_<destino>   |   destino guarda  from_<llamador>
Ningún servicio puede leer el camino de secretos de otro. Solo stdlib (se ejecuta en un contenedor python:slim).
Variables: VAULT_ADDR, VAULT_ROOT_TOKEN, VAULT_TOKEN_<SERVICIO>, PAYMENTS_WEBHOOK_SECRET (opcional).
"""
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.request

ADDR = os.environ.get("VAULT_ADDR", "http://vault:8200")
ROOT = os.environ["VAULT_ROOT_TOKEN"]

# (llamador, destino)
PAIRS = [
    ("gateway", "auth"), ("gateway", "clients"), ("gateway", "inventory"), ("gateway", "orders"),
    ("gateway", "payments"), ("gateway", "graphql"),
    ("auth", "clients"), ("orders", "inventory"), ("payments", "orders"),
    ("graphql", "orders"), ("graphql", "inventory"), ("graphql", "clients"),
]
SERVICES = ["gateway", "auth", "clients", "inventory", "orders", "payments", "graphql"]


def vault(method, path, body=None):
    req = urllib.request.Request(f"{ADDR}/v1/{path}", method=method, headers={"X-Vault-Token": ROOT},
                                 data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        print(f"Vault {method} {path} -> {e.code}", file=sys.stderr)
        raise


def wait():
    for _ in range(30):
        try:
            urllib.request.urlopen(f"{ADDR}/v1/sys/health", timeout=2)
            return
        except Exception:
            time.sleep(1)
    sys.exit("Vault no responde")


def main():
    wait()
    data = {s: {} for s in SERVICES}
    for caller, dest in PAIRS:
        key = secrets.token_urlsafe(32)
        data[caller][f"to_{dest}"] = key
        data[dest][f"from_{caller}"] = key
    data["payments"]["webhook_secret"] = os.environ.get("PAYMENTS_WEBHOOK_SECRET") or secrets.token_urlsafe(32)

    for svc in SERVICES:
        vault("POST", f"secret/data/{svc}", {"data": data[svc]})
        vault("PUT", f"sys/policies/acl/{svc}",
              {"policy": f'path "secret/data/{svc}" {{ capabilities = ["read"] }}'})
        tok = os.environ.get(f"VAULT_TOKEN_{svc.upper()}")
        if not tok:
            sys.exit(f"Falta VAULT_TOKEN_{svc.upper()}")
        try:
            vault("POST", "auth/token/create", {"id": tok, "policies": [svc], "no_default_policy": True,
                                                "ttl": "720h", "renewable": True})
        except urllib.error.HTTPError as e:
            if e.code == 400:
                pass
            else:
                raise
    print("Vault inicializado: secretos y tokens por servicio creados")


if __name__ == "__main__":
    main()
