import argparse
import json
import socket
import threading
import time
from typing import Optional


def rendezvous_request(rendezvous_host, rendezvous_port, local_port, payload):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", local_port))
    s.connect((rendezvous_host, rendezvous_port))
    s.sendall((json.dumps(payload) + "\n").encode())
    f = s.makefile("r")
    line = f.readline()
    s.close()
    return json.loads(line)


def get_own_address(rendezvous_host, rendezvous_port, local_port):
    data = rendezvous_request(rendezvous_host, rendezvous_port, local_port,
                               {"cmd": "whoami"})
    return tuple(data["you"])


def get_peer_via_room(rendezvous_host, rendezvous_port, room, password, local_port):
    payload = {"cmd": "room", "room": room, "local_port": local_port}
    if password:
        payload["password"] = password
    data = rendezvous_request(rendezvous_host, rendezvous_port, local_port, payload)
    if "error" in data:
        raise RuntimeError(f"Рандеву-сервер отказал: {data['error']}")
    return tuple(data["you"]), tuple(data["peer"])


def punch(sock: socket.socket, peer_addr, stop_event, interval=0.5):
    """Постоянно шлём пустые пакеты пиру, пока не установим соединение."""
    msg = b"punch"
    while not stop_event.is_set():
        try:
            sock.sendto(msg, peer_addr)
        except OSError:
            pass
        time.sleep(interval)


def parse_addr(s: str) -> tuple[Optional[str], int]:
    if not s:
        return (None, 0)
    host, port = s.rsplit(":", 1)
    return host, int(port)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rendezvous", required=True, help="host:port рандеву-сервера")
    ap.add_argument("--mode", choices=["room", "manual"], default="room")
    ap.add_argument("--room", help="имя комнаты (режим room)")
    ap.add_argument("--password", default=None, help="пароль комнаты (опционально)")
    ap.add_argument("--peer", help="host:port собеседника (режим manual)")
    ap.add_argument("--local-port", type=int, default=0,
                     help="локальный UDP-порт (0 = случайный, но тогда whoami "
                          "будет бесполезен в manual-режиме)")
    args = ap.parse_args()

    rhost, rport = parse_addr(args.rendezvous)

    if args.mode == "room" and not args.room:
        ap.error("--room обязателен в режиме room")
    if args.mode == "manual" and not args.peer:
        ap.error("--peer обязателен в режиме manual")

    local_port = args.local_port

    if args.mode == "room":
        you, peer = get_peer_via_room(rhost, rport, args.room, args.password, local_port)
        peer_addr = (peer[0], peer[1])
    else:
        you = get_own_address(rhost, rport, local_port)
        peer_addr = parse_addr(args.peer)

    print(f"[*] Я снаружи выгляжу как {you[0]}:{you[1]}")
    print(f"[*] Адрес пира: {peer_addr[0]}:{peer_addr[1]}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", local_port))
    print(f"[*] Локальный UDP-сокет: 0.0.0.0:{sock.getsockname()[1]}")

    stop_event = threading.Event()
    puncher = threading.Thread(target=punch, args=(sock, peer_addr, stop_event),
                                daemon=True)
    puncher.start()

    connected = False
    sock.settimeout(1.0)
    print("[*] Пробиваем NAT, ждём ответ от пира...")
    while True:
        try:
            data, addr = sock.recvfrom(4096)
        except socket.timeout:
            continue
        except KeyboardInterrupt:
            break

        if not connected:
            connected = True
            stop_event.set()  # хватит спам-пакетов, канал открыт
            print(f"[+] Пробили NAT! Получен пакет от {addr}: {data!r}")

        if data != b"punch":
            print(f"[<] {addr}: {data!r}")

        if addr == peer_addr and data != b"punch":
            sock.sendto(b"ack:" + data, addr)


if __name__ == "__main__":
    main()