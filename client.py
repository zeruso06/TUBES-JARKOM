import socket
import time
import webbrowser

# ─── KONFIGURASI ─────────────────────────────────────────────
PROXY_HOST    = "192.168.1.17"   # Ganti IP laptop Proxy
PROXY_PORT    = 8080

SERVER_HOST   = "192.168.1.17"    # Ganti IP laptop Web Server
SERVER_UDP_PORT = 9000

UDP_COUNT   = 10
UDP_TIMEOUT = 1.0
# ─────────────────────────────────────────────────────────────


def http_client(path="/index.html"):
    """Mode TCP: kirim HTTP GET ke Proxy, tampilkan response."""
    print(f"\n[TCP] Menghubungi Proxy {PROXY_HOST}:{PROXY_PORT}")
    print(f"[TCP] Requesting: GET {path}\n")

    try:
        # Buat socket TCP
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((PROXY_HOST, PROXY_PORT))

        # Susun dan kirim HTTP request
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {PROXY_HOST}:{PROXY_PORT}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        )
        sock.sendall(request.encode())

        # Terima response
        response = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk

        sock.close()

        # Tampilkan hasil
        response_text = response.decode(errors="replace")
        if "\r\n\r\n" in response_text:
            header, body = response_text.split("\r\n\r\n", 1)
            print("─── HEADER ───────────────────────────")
            print(header)
            print("─── BODY (100 karakter pertama) ───────")
            print(body[:100], "...")
        # Buka browser otomatis jika 200 OK
        if "200 OK" in header:
            url = f"http://{PROXY_HOST}:{PROXY_PORT}{path}"
            print(f"\n[INFO] Membuka browser: {url}")
            webbrowser.open(url)
        else:
            print(response_text[:200])

    except ConnectionRefusedError:
        print("[ERROR] Koneksi ditolak. Pastikan Proxy sudah berjalan.")
    except socket.timeout:
        print("[ERROR] Timeout. Proxy tidak merespons.")
    except Exception as e:
        print(f"[ERROR] {e}")


def udp_pinger():
    """Mode UDP: kirim paket ke Server, tampilkan RTT tiap paket."""
    print(f"\n[UDP] Ping ke {SERVER_HOST}:{SERVER_UDP_PORT}")
    print(f"[UDP] Mengirim {UDP_COUNT} paket...\n")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(UDP_TIMEOUT)

    for seq in range(1, UDP_COUNT + 1):
        send_time = time.time()
        payload = f"Ping {seq} {send_time:.6f}".encode()

        try:
            sock.sendto(payload, (SERVER_HOST, SERVER_UDP_PORT))
            data, _ = sock.recvfrom(1024)
            rtt_ms = (time.time() - send_time) * 1000
            print(f"  Paket {seq:>2}: RTT = {rtt_ms:.2f} ms")

        except socket.timeout:
            print(f"  Paket {seq:>2}: Request timed out")

        time.sleep(0.2)

    sock.close()
    print("\n[UDP] Selesai.")


def main():
    print("=" * 45)
    print("  Client HTTP + UDP Pinger")
    print("=" * 45)
    print("  [1] Mode TCP  - HTTP GET via Proxy")
    print("  [2] Mode UDP  - QoS Ping ke Server")
    print("=" * 45)

    pilihan = input("Pilih mode (1/2): ").strip()

    if pilihan == "1":
        path = input("Path yang diminta (Enter untuk /index.html): ").strip()
        if not path:
            path = "/index.html"
        http_client(path)

    elif pilihan == "2":
        udp_pinger()

    else:
        print("[ERROR] Pilihan tidak valid. Masukkan 1 atau 2.")


if __name__ == "__main__":
    main()