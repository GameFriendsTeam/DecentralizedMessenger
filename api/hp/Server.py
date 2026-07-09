import argparse
import json
import socket
import threading

rooms_lock = threading.Lock()
# room_name -> {"password": str|None, "peers": [(conn, addr, local_port), ...]}
rooms = {}


def send_json(conn: socket.socket, obj: dict):
    try:
        conn.sendall((json.dumps(obj) + "\n").encode())
    except OSError:
        pass


def handle_room(conn, addr, req):
    room = req["room"]
    password = req.get("password") or None
    local_port = int(req.get("local_port", addr[1]))

    with rooms_lock:
        entry = rooms.setdefault(room, {"password": password, "peers": []})

        if entry["password"] != password:
            send_json(conn, {"error": "bad password"})
            conn.close()
            print(f"[!] {addr} получил отказ по паролю для комнаты '{room}'")
            return

        entry["peers"].append((conn, addr, local_port))
        peers = entry["peers"]
        print(f"[+] {addr} присоединился к комнате '{room}' ({len(peers)}/2)")

        if len(peers) == 2:
            (conn_a, addr_a, port_a), (conn_b, addr_b, port_b) = peers

            payload_a = {"you": [addr_a[0], port_a], "peer": [addr_b[0], port_b]}
            payload_b = {"you": [addr_b[0], port_b], "peer": [addr_a[0], port_a]}

            for c, payload in ((conn_a, payload_a), (conn_b, payload_b)):
                send_json(c, payload)
                c.close()

            del rooms[room]
            print(f"[=] Комната '{room}' закрыта, адреса разосланы")


def handle_client(conn: socket.socket, addr):
    try:
        conn.settimeout(30)
        f = conn.makefile("r")
        line = f.readline()
        if not line:
            conn.close()
            return
        req = json.loads(line)
        cmd = req.get("cmd", "room")  # по умолчанию — старое поведение (комната)

        if cmd == "whoami":
            send_json(conn, {"you": [addr[0], addr[1]]})
            conn.close()
            print(f"[*] whoami для {addr}")
        elif cmd == "room":
            handle_room(conn, addr, req)
        else:
            send_json(conn, {"error": f"unknown cmd '{cmd}'"})
            conn.close()
    except Exception as e:
        print(f"[!] Ошибка с {addr}: {e}")
        try:
            conn.close()
        except OSError:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=9000)
    args = ap.parse_args()

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((args.host, args.port))
    srv.listen(16)
    print(f"[*] Rendezvous-сервер слушает {args.host}:{args.port}")

    while True:
        conn, addr = srv.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()


if __name__ == "__main__":
    main()