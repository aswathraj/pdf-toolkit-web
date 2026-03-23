from __future__ import annotations

import socket
import threading
import webbrowser
from contextlib import closing
from tkinter import Tk, messagebox, ttk

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


def main() -> None:
    port = find_available_port()
    server = LocalServerThread(HOST, port)
    server.start()
    url = f"http://{HOST}:{port}"

    root = Tk()
    root.title("PDF Forge")
    root.geometry("520x260")
    root.resizable(False, False)

    frame = ttk.Frame(root, padding=20)
    frame.pack(fill="both", expand=True)

    title = ttk.Label(frame, text="PDF Forge", font=("Segoe UI", 18, "bold"))
    title.pack(anchor="w")

    summary = ttk.Label(
        frame,
        text="The local document server is running. Use the button below to open the app in your browser.",
        wraplength=460,
        justify="left",
    )
    summary.pack(anchor="w", pady=(8, 12))

    ttk.Label(frame, text=f"App URL: {url}", wraplength=460, justify="left").pack(anchor="w", pady=(0, 6))
    ttk.Label(
        frame,
        text=f"Stored files: {DATA_DIR}",
        wraplength=460,
        justify="left",
    ).pack(anchor="w", pady=(0, 18))

    button_row = ttk.Frame(frame)
    button_row.pack(anchor="w", pady=(0, 12))

    def open_browser() -> None:
        webbrowser.open(url)

    def shutdown() -> None:
        try:
            server.stop()
        finally:
            root.destroy()

    ttk.Button(button_row, text="Open PDF Forge", command=open_browser).pack(side="left", padx=(0, 10))
    ttk.Button(button_row, text="Exit", command=shutdown).pack(side="left")

    ttk.Label(
        frame,
        text="OCR works when Tesseract is installed or bundled next to the app.",
        wraplength=460,
        justify="left",
    ).pack(anchor="w")

    root.protocol("WM_DELETE_WINDOW", shutdown)
    root.after(900, open_browser)

    try:
        root.mainloop()
    except Exception as exc:  # pragma: no cover - GUI fallback
        server.stop()
        messagebox.showerror("PDF Forge", str(exc))


if __name__ == "__main__":
    main()
