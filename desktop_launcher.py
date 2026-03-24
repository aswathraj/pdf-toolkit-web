from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from contextlib import closing
from pathlib import Path

os.environ["PDF_FORGE_DESKTOP"] = "1"
import webview
from werkzeug.serving import make_server

from app import DATA_DIR, app


HOST = "127.0.0.1"


def find_available_port(start: int = 5050, end: int = 5099) -> int:
    for port in range(start, end + 1):
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if sock.connect_ex((HOST, port)) != 0:
                return port
    raise RuntimeError("No free local ports were found between 5050 and 5099.")


def wait_for_server(url: str, timeout_seconds: float = 15.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/health", timeout=0.5) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.15)
    raise RuntimeError("The local PDF Forge server did not become ready in time.")


class LocalServerThread(threading.Thread):
    def __init__(self, host: str, port: int) -> None:
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.server = make_server(host, port, app, threaded=True)

    def run(self) -> None:
        self.server.serve_forever()

    def stop(self) -> None:
        self.server.shutdown()


class DesktopBridge:
    def _normalize_path(self, raw_path: str) -> Path:
        resolved = Path(raw_path).expanduser().resolve()
        data_root = DATA_DIR.resolve()
        if data_root not in resolved.parents and resolved != data_root:
            raise ValueError("Path is outside the app data directory.")
        if not resolved.exists():
            raise FileNotFoundError(f"Path not found: {resolved}")
        return resolved

    def open_path(self, raw_path: str) -> bool:
        path = self._normalize_path(raw_path)
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
            return True
        if sys.platform == "win32":
            os.startfile(str(path))
            return True
        subprocess.Popen(["xdg-open", str(path)])
        return True

    def reveal_path(self, raw_path: str) -> bool:
        path = self._normalize_path(raw_path)
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)])
            return True
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", str(path)])
            return True
        target = path if path.is_dir() else path.parent
        subprocess.Popen(["xdg-open", str(target)])
        return True


def open_fallback_browser(url: str) -> None:
    webbrowser.open(url)


def main() -> None:
    port = find_available_port()
    server = LocalServerThread(HOST, port)
    server.start()
    url = f"http://{HOST}:{port}"

    try:
        wait_for_server(url)
    except Exception:
        server.stop()
        raise

    window = webview.create_window(
        "PDF Forge by Aswath Raj",
        url,
        min_size=(1120, 760),
        width=1380,
        height=900,
        text_select=True,
        confirm_close=True,
        js_api=DesktopBridge(),
    )

    def handle_closed() -> None:
        server.stop()

    window.events.closed += handle_closed

    try:
        webview.start(
            debug=False,
            storage_path=str(DATA_DIR / "webview-storage"),
            private_mode=False,
        )
    except Exception:
        server.stop()
        open_fallback_browser(url)
        raise


if __name__ == "__main__":
    main()
