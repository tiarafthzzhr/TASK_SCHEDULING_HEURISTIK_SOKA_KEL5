"""Install pinned kind and kubectl binaries locally; no sudo required."""
import hashlib
import os
from pathlib import Path
import platform
import urllib.request

VERSION = "v0.33.0"
KUBECTL_VERSION = "v1.37.0"


def download(url, checksum_url, target):
    print(f"Download {target.name} ke {target}", flush=True)
    checksum = urllib.request.urlopen(checksum_url, timeout=60).read().decode().split()[0]
    payload = urllib.request.urlopen(url, timeout=120).read()
    if hashlib.sha256(payload).hexdigest() != checksum:
        raise SystemExit(f"Checksum {target.name} tidak cocok; binary tidak disimpan")
    target.write_bytes(payload)
    if os.name != "nt":
        target.chmod(0o755)


def main():
    system = {"Linux": "linux", "Windows": "windows"}.get(platform.system())
    if system is None or platform.machine().lower() not in ("x86_64", "amd64"):
        raise SystemExit("Installer ini untuk Linux/Windows x86_64; gunakan panduan resmi kind untuk platform lain.")
    name = f"kind-{system}-amd64"
    if system == "windows":
        name += ".exe"
    base = f"https://github.com/kubernetes-sigs/kind/releases/download/{VERSION}/"
    folder = Path(__file__).resolve().parents[1] / ".tools" / "kubernetes-bin"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / ("kind.exe" if system == "windows" else "kind")
    download(base + name, base + name + ".sha256sum", target)
    kubectl_name = "kubectl.exe" if system == "windows" else "kubectl"
    url = f"https://dl.k8s.io/release/{KUBECTL_VERSION}/bin/{system}/amd64/{kubectl_name}"
    download(url, url + ".sha256", folder / kubectl_name)
    print("kind dan kubectl siap; lanjutkan python3 kube_backend.py setup")


if __name__ == "__main__":
    main()
