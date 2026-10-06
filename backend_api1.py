from fastapi import (
    FastAPI,
    Header,
    HTTPException,
    Depends
)

import os
import secrets

app = FastAPI(
    title="Protected Backend API es",
    description="API ubicada y enrutada por API gateway"
)

#SELINUX 
INTERNAL_GATEWAY_SECRET = os.getenv(
    "INTERNAL_GATEWAY_SECRET"
)

if not INTERNAL_GATEWAY_SECRET:
    raise RuntimeError("INTERNAL_GATEWAY_SECRET no esta configurado"
    )

def verify_gateway(
        x_gateway_secret: str = Header(default="")
        ):
    valid = secrets.compare_digest(
        x_gateway_secret,
        INTERNAL_GATEWAY_SECRET
    )
    if not valid:
        raise HTTPException(
            status_code=403,
            detail="Solicitud no autorizada"
        )


@app.get(
        "/health",
        dependencies=[Depends(verify_gateway)]
        )
def health(
    x_authenticated_client: str | None = Header(
        default=None
        )
    ):
    return {
        "authenticated_client": x_authenticated_client,
        "status": "OK",
        "service": "Backend API"
    }

@app.get(
        "/products",
        dependencies=[Depends(verify_gateway)]
        )
def products(
    x_authenticated_client: str | None = Header(default=None),
    x_authenticated_user: str | None = Header(default=None),
    x_authenticated_roles: str | None = Header(default=None)
):

    return {
        "identity": {
            "client": x_authenticated_client,
            "user": x_authenticated_user,
            "roles": x_authenticated_roles
        },  
        "productos": [
            {"id": 1, "nombre": "Notebook", "precio": 900000},
            {"id": 2, "nombre": "Monitor", "precio": 250000}
        ]
    }

@app.get(
        "/ordenes",
        dependencies=[Depends(verify_gateway)]
        )
def orders(
    x_authenticated_client: str | None = Header(default=None),
    x_authenticated_user: str | None = Header(default=None),
    x_authenticated_roles: str | None = Header(default=None)
    ):
    return {
        "identity": {
            "client": x_authenticated_client,
            "user": x_authenticated_user,
            "roles": x_authenticated_roles
        },
        "ordenes": [
            {"id": 1001, "status": "paid"},
            {"id": 1002, "status": "pending"}
        ]
    }

@app.delete("/products/{product_id}", dependencies=[Depends(verify_gateway)])
def delete_product(
    product_id: str,
    x_authenticated_roles: str | None = Header(default=None)
):
    roles = [r.strip() for r in (x_authenticated_roles or "").split(",") if r.strip()]
    if "admin" not in roles:
        raise HTTPException(
            status_code=403,
            detail="Operación denegada: requiere rol admin"
        )
    return {
        "message": f"Producto {product_id} eliminado exitosamente",
        "deleted_id": product_id
    }