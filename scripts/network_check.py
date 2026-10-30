"""Before K3s install: test TCP 18080 and real Flannel UDP port 8472 both ways."""
import argparse
import json
import secrets
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import ProxyHandler, build_opener

MARKER = "soka-wsl-network-check"


def serve():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({"service": MARKER, "hostname": socket.gethostname()}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp, ThreadingHTTPServer(("0.0.0.0", 18080), Handler) as tcp:
        udp.bind(("0.0.0.0", 8472))
        def udp_echo():
            while True:
                payload, sender = udp.recvfrom(2048)
                udp.sendto(MARKER.encode() + b":" + payload, sender)
        threading.Thread(target=udp_echo, daemon=True).start()
        print("Test server: TCP 18080, UDP 8472. Stop with Ctrl+C before installing K3s.", flush=True)
        tcp.serve_forever()


def check(peer):
    opener = build_opener(ProxyHandler({}))
    with opener.open(f"http://{peer}:18080/", timeout=5) as response:
        data = json.load(response)
    if data.get("service") != MARKER:
        raise ValueError("TCP endpoint is not the WSL test server")
    nonce = secrets.token_bytes(16)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
        udp.settimeout(5)
        udp.connect((peer, 8472))
        udp.send(nonce)
        reply = udp.recv(2048)
        if reply != MARKER.encode() + b":" + nonce:
            raise ValueError("Unexpected UDP response")
    print(f"PASS: {peer}, TCP 18080 and UDP 8472; peer hostname: {data['hostname']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["serve", "check"])
    parser.add_argument("peer", nargs="?")
    args = parser.parse_args()
    if args.mode == "check" and not args.peer:
        parser.error("Provide the other laptop's reachable Wi-Fi IP")
    try:
        serve() if args.mode == "serve" else check(args.peer)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"FAIL: {exc}\nDo not install/join K3s before network checks pass both ways.\n")
