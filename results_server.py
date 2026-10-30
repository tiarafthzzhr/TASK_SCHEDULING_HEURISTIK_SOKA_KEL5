"""Read-only results browser; serves only the output volume, never kubeconfig."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", default="/results")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    directory = Path(args.directory).resolve()
    if not directory.is_dir():
        parser.error("Results directory does not exist")
    handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
    with ThreadingHTTPServer(("0.0.0.0", args.port), handler) as server:
        print(f"Read-only results on port {args.port}", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
