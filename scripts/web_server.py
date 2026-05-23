from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import posixpath
import sys
from typing import Any
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.llm_client import LLMError
from scripts.nl_command_eval import EvalCase, evaluate_case

MAX_JSON_BYTES = 16 * 1024
SAFE_STATIC_EXACT = {"/", "/index.html", "/docs/1.0_EVIDENCE.json"}
SAFE_STATIC_PREFIXES = ("/web/", "/docs/figures/")


class DemoHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, directory: str | None = None, **kwargs: Any) -> None:
        super().__init__(*args, directory=directory or str(ROOT), **kwargs)

    def do_GET(self) -> None:
        if self.path == "/api/health":
            self._send_json({"ok": True, "mode": "live-llm"})
            return
        if not self._is_allowed_static_path():
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return
        super().do_GET()

    def do_HEAD(self) -> None:
        if not self._is_allowed_static_path():
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return
        super().do_HEAD()

    def do_POST(self) -> None:
        if self.path != "/api/command":
            self.send_error(HTTPStatus.NOT_FOUND, "Unknown endpoint")
            return

        try:
            self._validate_local_post()
            payload = self._read_json()
            command = str(payload.get("command", ""))
            runs = int(payload.get("runs", 1000))
            seed = int(payload.get("seed", 42))
            jitter = int(payload.get("jitter", 1))
            runs = max(1, min(runs, 10000))
            result = evaluate_case(EvalCase("live_command", command), runs, seed, jitter)
            self._send_json({"ok": True, "result": result})
        except LLMError as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.SERVICE_UNAVAILABLE)
        except Exception as exc:  # Keep the browser response readable during demo iteration.
            self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def _validate_local_post(self) -> None:
        content_type = self.headers.get("Content-Type", "").lower().split(";", 1)[0].strip()
        if content_type != "application/json":
            raise ValueError("Content-Type must be application/json")

        length = int(self.headers.get("Content-Length", "0") or 0)
        if length > MAX_JSON_BYTES:
            raise ValueError(f"JSON body too large; max {MAX_JSON_BYTES} bytes")

        origin = self.headers.get("Origin")
        host = self.headers.get("Host", "")
        port = self.server.server_port
        allowed_origins = {
            f"http://{host}",
            f"http://127.0.0.1:{port}",
            f"http://localhost:{port}",
            f"http://[::1]:{port}",
        }
        if origin and origin not in allowed_origins:
            raise ValueError("Cross-origin requests are not allowed")

    def _is_allowed_static_path(self) -> bool:
        path = unquote(urlsplit(self.path).path)
        normalized = posixpath.normpath(path)
        if not normalized.startswith("/"):
            normalized = f"/{normalized}"
        if path.endswith("/") and normalized != "/":
            normalized = f"{normalized}/"
        parts = [part for part in normalized.split("/") if part]
        if any(part.startswith(".") for part in parts):
            return False
        return normalized in SAFE_STATIC_EXACT or normalized in ("/web", "/docs/figures") or normalized.startswith(SAFE_STATIC_PREFIXES)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length)
        if not raw:
            return {}
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("JSON body must be an object")
        return data

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local web demo with a live LLM command endpoint.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), DemoHandler)
    print(f"Serving live demo at http://{args.host}:{args.port}/web/")
    print("POST /api/command calls the configured LLM and returns policy + win-rate stats.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
