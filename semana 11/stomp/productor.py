import argparse
import json
from decimal import Decimal, InvalidOperation
import xml.etree.ElementTree as ET
import stomp

DESTINO = "/queue/cola_pedidos"

def construir_mensaje(formato: str, pedido: dict, texto: str) -> tuple[str, str]:
    formato = formato.lower()
    
    if formato == "texto":
        return texto, "text/plain; charset=utf-8"

    elif formato == "fijo":
        id_str = str(pedido["id"]).zfill(6)[:6]
        cliente_str = str(pedido["cliente"]).ljust(20)[:20]
        monto_str = f"{pedido['monto']:010.2f}"
        
        cuerpo = f"{id_str}{cliente_str}{monto_str}"
        return cuerpo, "text/plain; charset=utf-8"

    elif formato == "json":
        cuerpo = json.dumps({
            "id": pedido["id"],
            "cliente": pedido["cliente"],
            "monto": float(pedido["monto"])
        })
        return cuerpo, "application/json"

    elif formato == "xml":
        raiz = ET.Element("pedido")
        
        id_elem = ET.SubElement(raiz, "id")
        id_elem.text = str(pedido["id"])
        
        cliente_elem = ET.SubElement(raiz, "cliente")
        cliente_elem.text = str(pedido["cliente"])
        
        monto_elem = ET.SubElement(raiz, "monto")
        monto_elem.text = f"{pedido['monto']:.2f}"
        
        cuerpo = ET.tostring(raiz, encoding="utf-8").decode("utf-8")
        return cuerpo, "application/xml"

    else:
        raise ValueError(f"Formato no soportado: {formato}")


def main():
    parser = argparse.ArgumentParser(description="Productor STOMP - ActiveMQ")
    
    parser.add_argument("--formato", choices=["texto", "fijo", "xml", "json"], required=True, help="Formato del mensaje")
    parser.add_argument("--mensaje", default="Hola desde el productor Stomp", help="Mensaje para formato texto libre")
    parser.add_argument("--id", default="123", help="ID del pedido")
    parser.add_argument("--cliente", default="Ernesto Yanco", help="Nombre del cliente")
    parser.add_argument("--monto", default="123.45", help="Monto del pedido")
    
    parser.add_argument("--host", default="127.0.0.1", help="Host del broker")
    parser.add_argument("--port", type=int, default=61613, help="Puerto STOMP de ActiveMQ")
    parser.add_argument("--usuario", default="admin", help="Usuario del broker")
    parser.add_argument("--clave", default="admin", help="Clave del broker")
    
    args = parser.parse_args()

    try:
        monto = Decimal(args.monto)
        if not monto.is_finite() or monto < 0:
            raise ValueError("El monto debe ser un número finito positivo")
    except (InvalidOperation, ValueError) as e:
        parser.error(f"Monto no válido: {args.monto} ({e})")

    pedido = {
        "id": args.id,
        "cliente": args.cliente,
        "monto": monto
    }

    try:
        cuerpo, mime = construir_mensaje(args.formato, pedido, args.mensaje)
    except ValueError as e:
        parser.error(str(e))

    conexion = stomp.Connection12([(args.host, args.port)])
    try:
        conexion.connect(args.usuario, args.clave, wait=True)
        
        headers = {
            "destination": DESTINO,
            "content-type": mime,
            "x-formato": args.formato,
            "persistent": "true"
        }
        
        conexion.send(
            destination=DESTINO,
            body=cuerpo,
            headers=headers
        )
        print(f"Mensaje enviado a {DESTINO} [formato={args.formato}]:")
        print(cuerpo)

    except Exception as e:
        print(f"Error al enviar mensaje a ActiveMQ: {e}")
    finally:
        if conexion.is_connected():
            conexion.disconnect()


if __name__ == "__main__":
    main()