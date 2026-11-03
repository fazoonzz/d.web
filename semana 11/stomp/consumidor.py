import time
import json
from decimal import Decimal, InvalidOperation
import xml.etree.ElementTree as ET
import stomp

DESTINO = "/queue/cola_pedidos"

def interpretar(cuerpo: str, formato: str) -> dict:
    formato = (formato or "").lower()

    if formato == "texto":
        return {"tipo": "texto", "contenido": cuerpo}

    elif formato == "fijo":
        if len(cuerpo) != 36:
            raise ValueError(f"Longitud inválida para formato fijo: se esperaban 36 caracteres, se recibieron {len(cuerpo)}")
        id_str = cuerpo[0:6].strip()
        cliente_str = cuerpo[6:26].strip()
        monto_str = cuerpo[26:36].strip()
        
        try:
            monto = float(Decimal(monto_str))
        except (InvalidOperation, ValueError):
            raise ValueError(f"Monto no numérico en formato fijo: '{monto_str}'")

        return {
            "tipo": "fijo",
            "id": id_str,
            "cliente": cliente_str,
            "monto": monto
        }

    elif formato == "json":
        data = json.loads(cuerpo)
        if not all(k in data for k in ("id", "cliente", "monto")):
            raise ValueError("JSON no contiene las claves requeridas ('id', 'cliente', 'monto')")
        return {
            "tipo": "json",
            "id": str(data["id"]),
            "cliente": data["cliente"],
            "monto": float(data["monto"])
        }

    elif formato == "xml":
        raiz = ET.fromstring(cuerpo)
        if raiz.tag != "pedido":
            raise ValueError(f"Etiqueta raíz inválida en XML: <{raiz.tag}> (se esperaba <pedido>)")
        
        id_elem = raiz.find("id")
        cliente_elem = raiz.find("cliente")
        monto_elem = raiz.find("monto")

        if id_elem is None or cliente_elem is None or monto_elem is None:
            raise ValueError("XML incompleto: faltan etiquetas <id>, <cliente> o <monto>")

        return {
            "tipo": "xml",
            "id": id_elem.text,
            "cliente": cliente_elem.text,
            "monto": float(Decimal(monto_elem.text))
        }

    else:
        raise ValueError(f"Formato no reconocido: '{formato}'")


class EscuchadorPedidos(stomp.ConnectionListener):
    def __init__(self, conn):
        self.conn = conn

    def on_error(self, frame):
        print(f"[ERROR BROKER] {frame.body}")

    def on_message(self, frame):
        headers = frame.headers
        cuerpo = frame.body
        ack_id = headers.get("ack") or headers.get("message-id")
        formato = headers.get("x-formato") or "texto"

        print("\n" + "=" * 50)
        print(f"[MENSAJE RECIBIDO] ID: {headers.get('message-id')}")
        print(f"Formato declarado: {formato}")
        print(f"Cuerpo crudo:\n{cuerpo}")

        try:
            datos_procesados = interpretar(cuerpo, formato)
            print(f"[PROCESADO CON ÉXITO] {datos_procesados}")
            
            self.conn.ack(id=ack_id)
            print("[ACK ENVIADO] Mensaje confirmado y consumido.")
        except Exception as e:
            print(f"[ERROR DE VALIDACIÓN] {e}")
            
            self.conn.nack(id=ack_id)
            print("[NACK ENVIADO] Mensaje rechazado.")


def main():
    host = "127.0.0.1"
    port = 61613
    usuario = "admin"
    clave = "admin"

    conn = stomp.Connection12([(host, port)])
    escuchador = EscuchadorPedidos(conn)
    conn.set_listener("pedidos_listener", escuchador)

    try:
        conn.connect(usuario, clave, wait=True)
        print(f"Consumidor conectado a ActiveMQ ({host}:{port})")

        conn.subscribe(
            destination=DESTINO,
            id="sub_consumidor_pedidos",
            ack="client-individual"
        )
        print(f"Escuchando mensajes en {DESTINO}... (Presiona Ctrl+C para salir)\n")

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nDeteniendo consumidor...")
    finally:
        if conn.is_connected():
            conn.disconnect()
            print("Desconectado de ActiveMQ.")


if __name__ == "__main__":
    main()