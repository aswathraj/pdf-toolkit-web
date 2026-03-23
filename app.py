from __future__ import annotations

import os
import sys
import time
import uuid
import zipfile
from pathlib import Path

from flask import Flask, abort, flash, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

from services.document_tools import ProcessingError, TOOL_DEFINITIONS, run_tool


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def get_resource_dir() -> Path:
    if is_frozen() and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def get_data_dir() -> Path:
    if is_frozen():
        if sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / "PDF Forge"
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            return Path(local_appdata) / "PDF Forge"
        return Path.home() / ".pdf_forge"
    return Path(__file__).resolve().parent


RESOURCE_DIR = get_resource_dir()
DATA_DIR = get_data_dir()
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "outputs"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(
    __name__,
    template_folder=str(RESOURCE_DIR / "templates"),
    static_folder=str(RESOURCE_DIR / "static"),
)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "pdf-toolkit-dev-secret")
app.config["MAX_CONTENT_LENGTH"] = None


def is_desktop_mode() -> bool:
    return os.environ.get("PDF_FORGE_DESKTOP") == "1"


def cleanup_old_jobs(root: Path, ttl_seconds: int = 60 * 60 * 12) -> None:
    cutoff = time.time() - ttl_seconds
    for path in root.iterdir():
        try:
            if path.is_dir() and path.stat().st_mtime < cutoff:
                for child in sorted(path.rglob("*"), reverse=True):
                    if child.is_file():
                        child.unlink(missing_ok=True)
                    elif child.is_dir():
                        child.rmdir()
                path.rmdir()
        except OSError:
            continue


def save_uploads(files, destination: Path) -> list[Path]:
    saved_files: list[Path] = []
    destination.mkdir(parents=True, exist_ok=True)
    for file_storage in files:
        if not file_storage or not file_storage.filename:
            continue
        safe_name = secure_filename(file_storage.filename) or f"upload-{uuid.uuid4().hex}"
        target = destination / safe_name
        stem = target.stem
        suffix = target.suffix
        counter = 1
        while target.exists():
            target = destination / f"{stem}-{counter}{suffix}"
            counter += 1
        file_storage.save(target)
        saved_files.append(target)
    return saved_files


def package_outputs(job_output_dir: Path, result_files: list[Path], tool_key: str) -> Path:
    if len(result_files) == 1:
        return result_files[0]

    archive_path = job_output_dir / f"{tool_key}-bundle.zip"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_path in result_files:
            archive.write(file_path, arcname=file_path.name)
    return archive_path


def resolve_job_artifact(job_id: str, filename: str) -> Path:
    job_output_dir = (OUTPUT_DIR / job_id).resolve()
    artifact = (job_output_dir / filename).resolve()
    if not artifact.exists() or artifact.parent != job_output_dir:
        raise FileNotFoundError
    return artifact


@app.before_request
def prune_storage() -> None:
    cleanup_old_jobs(UPLOAD_DIR)
    cleanup_old_jobs(OUTPUT_DIR)


@app.get("/")
def index():
    return render_template("index.html", tools=TOOL_DEFINITIONS)


@app.context_processor
def inject_app_mode():
    return {"desktop_mode": is_desktop_mode()}


@app.post("/process/<tool_key>")
def process(tool_key: str):
    tool = next((tool for tool in TOOL_DEFINITIONS if tool["key"] == tool_key), None)
    if tool is None:
        flash("That tool is not available.", "error")
        return redirect(url_for("index"))

    uploaded_files = request.files.getlist("files")
    if not any(file.filename for file in uploaded_files):
        flash("Upload at least one file to continue.", "error")
        return redirect(url_for("index"))

    job_id = uuid.uuid4().hex
    job_upload_dir = UPLOAD_DIR / job_id
    job_output_dir = OUTPUT_DIR / job_id
    saved_files = save_uploads(uploaded_files, job_upload_dir)

    if not saved_files:
        flash("The uploaded files could not be saved.", "error")
        return redirect(url_for("index"))

    try:
        result = run_tool(
            tool_key=tool_key,
            files=saved_files,
            output_dir=job_output_dir,
            form_data=request.form,
        )
        artifact = package_outputs(job_output_dir, result.files, tool_key)
        if is_desktop_mode():
            return render_template(
                "result.html",
                artifact_name=artifact.name,
                artifact_path=str(artifact),
                artifact_dir=str(artifact.parent),
                download_url=url_for("download_artifact", job_id=job_id, filename=artifact.name),
            )
        return send_file(
            artifact,
            as_attachment=True,
            download_name=artifact.name,
            mimetype="application/octet-stream",
        )
    except ProcessingError as exc:
        flash(str(exc), "error")
        return redirect(url_for("index"))
    except Exception as exc:  # pragma: no cover - last-resort guard
        flash(f"Processing failed: {exc}", "error")
        return redirect(url_for("index"))


@app.get("/health")
def health():
    return {"status": "ok", "tools": len(TOOL_DEFINITIONS), "data_dir": str(DATA_DIR)}


@app.get("/download/<job_id>/<filename>")
def download_artifact(job_id: str, filename: str):
    try:
        artifact = resolve_job_artifact(job_id, filename)
    except FileNotFoundError:
        abort(404)

    return send_file(
        artifact,
        as_attachment=True,
        download_name=artifact.name,
        mimetype="application/octet-stream",
    )


def run_development_server() -> None:
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(debug=debug, host=host, port=port)


if __name__ == "__main__":
    run_development_server()
