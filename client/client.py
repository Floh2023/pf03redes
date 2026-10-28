"""Cliente de ejemplo para enviar tareas JSON al servidor TCP."""
from __future__ import annotations

import json
import socket
from typing import Any

HOST = "127.0.0.1"
PORT = 5000


def request(task: dict[str, Any], host: str = HOST, port: int = PORT, timeout: float = 5.0) -> dict[str, Any]:
    """Envía una tarea y espera su respuesta JSON."""
    payload = json.dumps(task, ensure_ascii=False).encode("utf-8") + b"\n"
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall(payload)
        received = bytearray()
        while b"\n" not in received:
            chunk = sock.recv(4096)
            if not chunk:
                raise ConnectionError("El servidor cerró la conexión antes de responder")
            received.extend(chunk)
            if len(received) > 64 * 1024:
                raise ValueError("La respuesta excede el tamaño permitido")
    line, _, _ = received.partition(b"\n")
    response = json.loads(line.decode("utf-8"))
    if not isinstance(response, dict):
        raise ValueError("El servidor devolvió una respuesta inválida")
    return response


def main() -> None:
    examples = [
        {"operation": "sum", "values": [4, 8, 15]},
        {"operation": "uppercase", "value": "hola desde el cliente"},
    ]
    for task in examples:
        try:
            print(json.dumps(request(task), ensure_ascii=False))
        except (OSError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            print(f"No se pudo completar la solicitud: {exc}")


if __name__ == "__main__":
    main()
