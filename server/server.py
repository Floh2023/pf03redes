"""Servidor TCP concurrente con protocolo JSON delimitado por nueva línea."""
from __future__ import annotations

import json
import logging
import socket
from concurrent.futures import ThreadPoolExecutor
from typing import Any

HOST = "0.0.0.0"
PORT = 5000
MAX_LINE_BYTES = 64 * 1024

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def process_task(task: dict[str, Any]) -> dict[str, Any]:
    """Procesa una tarea de demostración y devuelve un resultado serializable."""
    operation = task.get("operation")
    if operation == "sum":
        values = task.get("values")
        if not isinstance(values, list) or not all(
            isinstance(value, (int, float)) and not isinstance(value, bool)
            for value in values
        ):
            raise ValueError("'values' debe ser una lista de números")
        return {"result": sum(values)}
    if operation == "uppercase":
        value = task.get("value")
        if not isinstance(value, str):
            raise ValueError("'value' debe ser texto")
        return {"result": value.upper()}
    raise ValueError("Operación no soportada. Use 'sum' o 'uppercase'.")


def send_response(conn: socket.socket, response: dict[str, Any]) -> None:
    """Envía una respuesta JSON terminada en nueva línea."""
    conn.sendall(json.dumps(response, ensure_ascii=False).encode("utf-8") + b"\n")


def handle_client(conn: socket.socket, address: tuple[str, int], task_pool: ThreadPoolExecutor) -> None:
    """Lee y procesa solicitudes JSON de una conexión hasta que se cierre."""
    logger.info("Conexión de %s:%s", *address)
    buffer = bytearray()
    try:
        with conn:
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    if buffer:
                        send_response(conn, {"ok": False, "error": "Solicitud incompleta: falta newline"})
                    break
                buffer.extend(chunk)
                if len(buffer) > MAX_LINE_BYTES and b"\n" not in buffer:
                    send_response(conn, {"ok": False, "error": "Solicitud demasiado grande"})
                    break
                while b"\n" in buffer:
                    raw_line, _, remainder = buffer.partition(b"\n")
                    buffer = bytearray(remainder)
                    if len(raw_line) > MAX_LINE_BYTES:
                        send_response(conn, {"ok": False, "error": "Solicitud demasiado grande"})
                        continue
                    try:
                        request = json.loads(raw_line.decode("utf-8"))
                        if not isinstance(request, dict):
                            raise ValueError("La solicitud debe ser un objeto JSON")
                        result = task_pool.submit(process_task, request).result()
                        response = {"ok": True, **result}
                    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                        response = {"ok": False, "error": str(exc)}
                    except Exception:
                        logger.exception("Error procesando solicitud de %s", address)
                        response = {"ok": False, "error": "Error interno al procesar la tarea"}
                    send_response(conn, response)
    except (ConnectionError, OSError) as exc:
        logger.info("Conexión con %s cerrada: %s", address, exc)
    finally:
        logger.info("Fin de conexión %s:%s", *address)


def serve(host: str = HOST, port: int = PORT, connection_workers: int = 16, task_workers: int = 8) -> None:
    """Inicia el listener TCP hasta recibir Ctrl+C."""
    if connection_workers < 1 or task_workers < 1:
        raise ValueError("Los tamaños de los pools deben ser positivos")
    with ThreadPoolExecutor(max_workers=connection_workers, thread_name_prefix="connection") as connections, \
         ThreadPoolExecutor(max_workers=task_workers, thread_name_prefix="task") as tasks:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((host, port))
            listener.listen()
            logger.info("Servidor escuchando en %s:%s", host, port)
            try:
                while True:
                    conn, address = listener.accept()
                    try:
                        connections.submit(handle_client, conn, address, tasks)
                    except RuntimeError:
                        conn.close()
                        raise
            except KeyboardInterrupt:
                logger.info("Cierre solicitado; esperando tareas activas")


if __name__ == "__main__":
    serve()
