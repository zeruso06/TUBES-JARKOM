import socket
import threading
import os
import mimetypes
from datetime import datetime

# ─── KONFIGURASI ─────────────────────────────────────────────
HOST = "0.0.0.0"       # Dengarkan semua interface
TCP_PORT = 8000        # Port HTTP
UDP_PORT = 9000        # Port UDP echo

# Direktori root tempat file HTML berada
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATUS_DIR = os.path.join(BASE_DIR, "status")
# ─────────────────────────────────────────────────────────────


def log(client_ip, path, status_code):
    """Catat log setiap request."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {client_ip} | {path} | {status_code}")


def get_content_type(filepath):
    """Deteksi Content-Type berdasarkan ekstensi file."""
    mime, _ = mimetypes.guess_type(filepath)
    return mime or "application/octet-stream"


def build_response(status_code, status_text, body_bytes, content_type="text/html; charset=utf-8"):
    """Susun HTTP response dengan format yang valid."""
    header = (
        f"HTTP/1.1 {status_code} {status_text}\r\n"
        f"Content-Type: {content_type}\r\n"
        f"Content-Length: {len(body_bytes)}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    )
    return header.encode() + body_bytes


def read_file(filepath):
    """Baca file dari disk, return bytes."""
    with open(filepath, "rb") as f:
        return f.read()


def handle_http_request(conn, client_ip):
    """Tangani satu koneksi HTTP dari client/proxy."""
    try:
        # 1. Terima request
        raw = b""
        while b"\r\n\r\n" not in raw:
            chunk = conn.recv(1024)
            if not chunk:
                break
            raw += chunk

        if not raw:
            conn.close()
            return

        # 2. Parse baris pertama: "GET /index.html HTTP/1.1"
        request_line = raw.decode(errors="replace").split("\r\n")[0]
        parts = request_line.split(" ")

        if len(parts) < 2:
            # Request tidak valid
            body = read_file(os.path.join(STATUS_DIR, "500.html"))
            conn.sendall(build_response(500, "Internal Server Error", body))
            log(client_ip, "INVALID", 500)
            conn.close()
            return

        method = parts[0]
        path   = parts[1]

        # 3. Normalisasi path
        # "/" → "/index.html"
        if path == "/":
            path = "/index.html"

        # Hapus query string jika ada (?foo=bar)
        if "?" in path:
            path = path.split("?")[0]

        # 4. Tentukan filepath di disk
        filepath = os.path.join(BASE_DIR, path.lstrip("/"))

        # 5. Kirim file jika ada, atau error jika tidak
        if os.path.isfile(filepath):
            body = read_file(filepath)
            content_type = get_content_type(filepath)
            response = build_response(200, "OK", body, content_type)
            conn.sendall(response)
            log(client_ip, path, 200)

        else:
            # 404 Not Found
            error_file = os.path.join(STATUS_DIR, "404.html")
            body = read_file(error_file)
            conn.sendall(build_response(404, "Not Found", body))
            log(client_ip, path, 404)

    except Exception as e:
        # 500 Internal Server Error
        try:
            error_file = os.path.join(STATUS_DIR, "500.html")
            body = read_file(error_file)
            conn.sendall(build_response(500, "Internal Server Error", body))
            log(client_ip, "ERROR", 500)
        except:
            pass
        print(f"[ERROR] {e}")

    finally:
        conn.close()


def start_tcp_server():
    """Jalankan HTTP server TCP di port 8000."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Izinkan reuse port supaya tidak error saat restart
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, TCP_PORT))
    server.listen(10)
    print(f"[TCP] Web Server berjalan di port {TCP_PORT}")

    while True:
        conn, addr = server.accept()
        client_ip = addr[0]
        # Spawn thread baru untuk tiap koneksi
        t = threading.Thread(target=handle_http_request, args=(conn, client_ip))
        t.daemon = True
        t.start()


def start_udp_server():
    """Jalankan UDP echo server di port 9000."""
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind((HOST, UDP_PORT))
    print(f"[UDP] Echo Server berjalan di port {UDP_PORT}")

    while True:
        try:
            data, addr = server.recvfrom(1024)
            # Echo balik payload tanpa diubah
            server.sendto(data, addr)
            print(f"[UDP] Echo ke {addr[0]} | payload: {data.decode(errors='replace')}")
        except Exception as e:
            print(f"[UDP ERROR] {e}")


def main():
    print("=" * 50)
    print("  Web Server + UDP Echo Server")
    print("=" * 50)

    # Jalankan UDP server di thread terpisah
    udp_thread = threading.Thread(target=start_udp_server)
    udp_thread.daemon = True
    udp_thread.start()

    # TCP server jalan di main thread
    start_tcp_server()


if __name__ == "__main__":
    main()