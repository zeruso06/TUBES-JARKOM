import socket
import threading
import os
from datetime import datetime

# ─── KONFIGURASI ─────────────────────────────────────────────
HOST        = "0.0.0.0"
PROXY_PORT  = 8080

SERVER_HOST = "192.168.1.17"   # Ganti IP laptop Web Server
SERVER_PORT = 8000

CACHE_DIR   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
TIMEOUT     = 10
# ─────────────────────────────────────────────────────────────

# Lock untuk mencegah race condition saat tulis cache bersamaan
cache_lock = threading.Lock()


def log(client_ip, path, status):
    """Catat log proxy: IP, path, HIT/MISS, waktu."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {client_ip} | {path} | {status}")


def get_cache_filename(path):
    """Ubah URL path jadi nama file cache yang aman."""
    # "/index.html" → "cache/_index.html"
    # "/" → "cache/_root"
    safe = path.replace("/", "_").replace(".", "_")
    if safe == "_":
        safe = "_root"
    return os.path.join(CACHE_DIR, safe)


def is_cached(path):
    """Cek apakah response untuk path ini sudah ada di cache."""
    return os.path.isfile(get_cache_filename(path))


def save_cache(path, data):
    """Simpan raw HTTP response ke file cache."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    filename = get_cache_filename(path)
    with cache_lock:
        with open(filename, "wb") as f:
            f.write(data)


def load_cache(path):
    """Baca cache dari disk, return bytes."""
    filename = get_cache_filename(path)
    with cache_lock:
        with open(filename, "rb") as f:
            return f.read()


def forward_to_server(request_line, path, host_header):
    """Kirim request ke Web Server, return raw response bytes."""

    # Susun ulang HTTP request untuk dikirim ke server
    request = (
        f"{request_line}\r\n"
        f"Host: {SERVER_HOST}:{SERVER_PORT}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    )

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.settimeout(TIMEOUT)
    server_sock.connect((SERVER_HOST, SERVER_PORT))
    server_sock.sendall(request.encode())

    # Terima seluruh response
    response = b""
    while True:
        chunk = server_sock.recv(4096)
        if not chunk:
            break
        response += chunk

    server_sock.close()
    return response


def build_error_response(status_code, status_text):
    """Buat response error sederhana."""
    body = f"<h1>{status_code} {status_text}</h1>".encode()
    header = (
        f"HTTP/1.1 {status_code} {status_text}\r\n"
        f"Content-Type: text/html\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    )
    return header.encode() + body


def handle_client(conn, client_ip):
    """Tangani satu koneksi dari client."""
    try:
        # 1. Terima request dari client
        raw = b""
        while b"\r\n\r\n" not in raw:
            chunk = conn.recv(1024)
            if not chunk:
                break
            raw += chunk

        if not raw:
            conn.close()
            return

        decoded = raw.decode(errors="replace")
        lines = decoded.split("\r\n")
        request_line = lines[0]  # "GET /index.html HTTP/1.1"

        # 2. Parse path dari request line
        parts = request_line.split(" ")
        if len(parts) < 2:
            conn.sendall(build_error_response(400, "Bad Request"))
            conn.close()
            return

        path = parts[1]
        if path == "/":
            path = "/index.html"
        if "?" in path:
            path = path.split("?")[0]

        # Ambil Host header jika ada
        host_header = f"{SERVER_HOST}:{SERVER_PORT}"
        for line in lines[1:]:
            if line.lower().startswith("host:"):
                host_header = line.split(":", 1)[1].strip()
                break

        # 3. Cek cache
        if is_cached(path):
            # CACHE HIT: kirim dari file cache
            response = load_cache(path)
            conn.sendall(response)
            log(client_ip, path, "HIT")

        else:
            # CACHE MISS: forward ke web server
            try:
                response = forward_to_server(request_line, path, host_header)

                # Simpan ke cache hanya jika response 200 OK
                if response.startswith(b"HTTP/1.1 200"):
                    save_cache(path, response)

                conn.sendall(response)
                log(client_ip, path, "MISS")

            except socket.timeout:
                # Web server tidak merespons
                conn.sendall(build_error_response(504, "Gateway Timeout"))
                log(client_ip, path, "504")

            except ConnectionRefusedError:
                # Web server tidak bisa dihubungi
                conn.sendall(build_error_response(502, "Bad Gateway"))
                log(client_ip, path, "502")

            except Exception as e:
                conn.sendall(build_error_response(502, "Bad Gateway"))
                log(client_ip, path, "502")
                print(f"[ERROR] Forward gagal: {e}")

    except Exception as e:
        print(f"[ERROR] Handle client gagal: {e}")

    finally:
        conn.close()


def main():
    print("=" * 50)
    print("  Proxy Server")
    print("=" * 50)
    os.makedirs(CACHE_DIR, exist_ok=True)

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PROXY_PORT))
    server.listen(10)
    print(f"[PROXY] Listening di port {PROXY_PORT}")
    print(f"[PROXY] Forward ke {SERVER_HOST}:{SERVER_PORT}")
    print(f"[PROXY] Cache dir: {CACHE_DIR}\n")

    while True:
        conn, addr = server.accept()
        client_ip = addr[0]
        t = threading.Thread(target=handle_client, args=(conn, client_ip))
        t.daemon = True
        t.start()


if __name__ == "__main__":
    main()