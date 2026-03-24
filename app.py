from __future__ import annotations

import json
import os
import sys
import threading
import time
import uuid
import zipfile
from pathlib import Path

from flask import Flask, abort, flash, redirect, render_template, request, send_file, url_for
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename

from services.document_tools import ProcessingError, TOOL_DEFINITIONS, run_tool


GITHUB_REPO_URL = "https://github.com/aswathraj/pdf-toolkit-web"
LATEST_RELEASE_URL = f"{GITHUB_REPO_URL}/releases/latest"
WINDOWS_INSTALLER_URL = f"{LATEST_RELEASE_URL}/download/PDFForgeSetup.exe"
MAC_INSTALLER_URL = f"{LATEST_RELEASE_URL}/download/PDFForge-macOS.dmg"
WINDOWS_PORTABLE_URL = f"{LATEST_RELEASE_URL}/download/PDFForge.exe"


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
JOB_STATUS_FILENAME = "status.json"
JOB_TTL_SECONDS = 60 * 60 * 12
JOB_TTL_HOURS = JOB_TTL_SECONDS // 3600
JOB_STATUS_LOCK = threading.Lock()

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(
    __name__,
    template_folder=str(RESOURCE_DIR / "templates"),
    static_folder=str(RESOURCE_DIR / "static"),
)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1, x_proto=1, x_port=1)
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


def job_output_dir(job_id: str) -> Path:
    return OUTPUT_DIR / job_id


def job_status_path(job_id: str) -> Path:
    return job_output_dir(job_id) / JOB_STATUS_FILENAME


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True), encoding="utf-8")
    temp_path.replace(path)


def create_job_record(job_id: str, tool_key: str, filenames: list[str]) -> dict:
    now = time.time()
    payload = {
        "job_id": job_id,
        "tool_key": tool_key,
        "input_filenames": filenames,
        "status": "queued",
        "progress": 0.0,
        "detail": "Upload received. Waiting to start.",
        "error": "",
        "eta_seconds": None,
        "artifact_name": "",
        "artifact_size": 0,
        "result_message": "",
        "created_at": now,
        "started_at": None,
        "updated_at": now,
        "completed_at": None,
    }
    with JOB_STATUS_LOCK:
        write_json(job_status_path(job_id), payload)
    return payload


def load_job_record(job_id: str) -> dict:
    path = job_status_path(job_id)
    if not path.exists():
        raise FileNotFoundError
    return json.loads(path.read_text(encoding="utf-8"))


def update_job_record(job_id: str, **updates) -> dict:
    with JOB_STATUS_LOCK:
        payload = load_job_record(job_id)
        payload.update(updates)
        payload["updated_at"] = time.time()
        write_json(job_status_path(job_id), payload)
    return payload


def resolve_job_artifact(job_id: str, filename: str) -> Path:
    output_dir = job_output_dir(job_id).resolve()
    artifact = (output_dir / filename).resolve()
    if not artifact.exists() or artifact.parent != output_dir:
        raise FileNotFoundError
    return artifact


def humanize_bytes(size: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def humanize_duration(seconds: float | None) -> str:
    if seconds is None:
        return "Estimating..."
    remaining = max(0, int(round(seconds)))
    if remaining < 60:
        return f"about {remaining}s"
    minutes, secs = divmod(remaining, 60)
    if minutes < 60:
        return f"about {minutes}m {secs:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"about {hours}h {minutes:02d}m"


def get_tool_definition(tool_key: str):
    return next((tool for tool in TOOL_DEFINITIONS if tool["key"] == tool_key), None)


def serialize_job_record(payload: dict) -> dict:
    progress = max(0.0, min(float(payload.get("progress", 0.0)), 1.0))
    started_at = payload.get("started_at")
    elapsed_seconds = max(0.0, time.time() - started_at) if started_at else 0.0
    artifact_size = int(payload.get("artifact_size") or 0)
    return {
        **payload,
        "progress": progress,
        "progress_percent": int(round(progress * 100)),
        "eta_text": humanize_duration(payload.get("eta_seconds")),
        "elapsed_text": humanize_duration(elapsed_seconds),
        "artifact_size_text": humanize_bytes(artifact_size) if artifact_size else "",
    }


def render_result_page(job_id: str, tool: dict, payload: dict, artifact: Path) -> str:
    download_url = url_for("download_artifact", job_id=job_id, filename=artifact.name)
    return render_template(
        "result.html",
        active_page="home",
        tool=tool,
        artifact_name=artifact.name,
        artifact_path=str(artifact),
        artifact_dir=str(artifact.parent),
        artifact_size=humanize_bytes(artifact.stat().st_size),
        artifact_is_archive=artifact.suffix.lower() == ".zip",
        result_message=payload.get("result_message") or f"PDF Forge finished {tool['title'].lower()} and prepared your download.",
        download_url=download_url,
        retention_hours=JOB_TTL_HOURS,
    )


def run_job(job_id: str, tool_key: str, saved_files: list[Path], form_data: dict[str, str]) -> None:
    tool = get_tool_definition(tool_key)
    if tool is None:
        update_job_record(job_id, status="failed", error="That tool is not available.", detail="Job could not start.")
        return

    output_dir = job_output_dir(job_id)
    started_at = time.time()
    update_job_record(
        job_id,
        status="processing",
        started_at=started_at,
        detail="Preparing files",
        progress=0.01,
        eta_seconds=None,
        error="",
    )

    def progress_callback(progress: float, detail: str) -> None:
        eta_seconds = None
        if progress > 0.01 and progress < 1.0:
            elapsed = max(0.0, time.time() - started_at)
            eta_seconds = max(0, int(elapsed * (1.0 - progress) / progress))
        update_job_record(
            job_id,
            status="processing",
            progress=progress,
            detail=detail,
            eta_seconds=eta_seconds,
        )

    try:
        result = run_tool(
            tool_key=tool_key,
            files=saved_files,
            output_dir=output_dir,
            form_data=form_data,
            progress_callback=progress_callback,
        )
        progress_callback(0.97, "Packaging your download")
        artifact = package_outputs(output_dir, result.files, tool_key)
        update_job_record(
            job_id,
            status="completed",
            progress=1.0,
            detail="Ready to download",
            eta_seconds=0,
            artifact_name=artifact.name,
            artifact_size=artifact.stat().st_size,
            result_message=result.message,
            completed_at=time.time(),
        )
    except ProcessingError as exc:
        update_job_record(
            job_id,
            status="failed",
            detail="Processing failed",
            error=str(exc),
            eta_seconds=None,
        )
    except Exception as exc:  # pragma: no cover - last-resort guard
        update_job_record(
            job_id,
            status="failed",
            detail="Processing failed",
            error=f"Unexpected error: {exc}",
            eta_seconds=None,
        )


def start_job(job_id: str, tool_key: str, saved_files: list[Path], form_data: dict[str, str]) -> None:
    worker = threading.Thread(
        target=run_job,
        args=(job_id, tool_key, saved_files, form_data),
        daemon=True,
        name=f"pdf-forge-job-{job_id}",
    )
    worker.start()


@app.before_request
def prune_storage() -> None:
    cleanup_old_jobs(UPLOAD_DIR, ttl_seconds=JOB_TTL_SECONDS)
    cleanup_old_jobs(OUTPUT_DIR, ttl_seconds=JOB_TTL_SECONDS)


@app.get("/")
def index():
    return render_template("index.html", tools=TOOL_DEFINITIONS, active_page="home")


@app.get("/about")
def about():
    badges = sorted({tool["badge"] for tool in TOOL_DEFINITIONS})
    return render_template(
        "about.html",
        active_page="about",
        tool_count=len(TOOL_DEFINITIONS),
        tool_badges=badges,
    )


@app.get("/downloads")
def downloads():
    return render_template(
        "downloads.html",
        active_page="downloads",
        download_options=[
            {
                "platform": "Windows",
                "headline": "Windows installer",
                "summary": "Install PDF Forge with bundled OCR support and desktop shortcuts.",
                "format": "PDFForgeSetup.exe",
                "primary_url": WINDOWS_INSTALLER_URL,
                "secondary_url": WINDOWS_PORTABLE_URL,
                "primary_label": "Download installer",
                "secondary_label": "Portable EXE",
            },
            {
                "platform": "macOS",
                "headline": "macOS app installer",
                "summary": "Download the DMG for the desktop app with the same tool suite and blue UI.",
                "format": "PDFForge-macOS.dmg",
                "primary_url": MAC_INSTALLER_URL,
                "secondary_url": LATEST_RELEASE_URL,
                "primary_label": "Download DMG",
                "secondary_label": "View release",
            },
        ],
    )


@app.context_processor
def inject_app_mode():
    return {
        "creator_name": "Aswath Raj",
        "desktop_mode": is_desktop_mode(),
        "github_repo_url": GITHUB_REPO_URL,
        "job_retention_hours": JOB_TTL_HOURS,
        "latest_release_url": LATEST_RELEASE_URL,
        "mac_installer_url": MAC_INSTALLER_URL,
        "windows_installer_url": WINDOWS_INSTALLER_URL,
    }


@app.post("/process/<tool_key>")
def process(tool_key: str):
    tool = get_tool_definition(tool_key)
    if tool is None:
        flash("That tool is not available.", "error")
        return redirect(url_for("index"))

    uploaded_files = request.files.getlist("files")
    if not any(file.filename for file in uploaded_files):
        flash("Upload at least one file to continue.", "error")
        return redirect(url_for("index"))

    job_id = uuid.uuid4().hex
    upload_dir = UPLOAD_DIR / job_id
    saved_files = save_uploads(uploaded_files, upload_dir)

    if not saved_files:
        flash("The uploaded files could not be saved.", "error")
        return redirect(url_for("index"))

    create_job_record(job_id, tool_key, [path.name for path in saved_files])
    start_job(job_id, tool_key, saved_files, request.form.to_dict(flat=True))
    return redirect(url_for("job_detail", job_id=job_id))


@app.get("/jobs/<job_id>")
def job_detail(job_id: str):
    try:
        payload = serialize_job_record(load_job_record(job_id))
    except FileNotFoundError:
        abort(404)

    tool = get_tool_definition(payload["tool_key"])
    if tool is None:
        abort(404)

    if payload["status"] == "completed" and payload.get("artifact_name"):
        return redirect(url_for("job_result", job_id=job_id))

    return render_template(
        "job.html",
        active_page="home",
        tool=tool,
        job_id=job_id,
        status_url=url_for("job_status", job_id=job_id),
        result_url=url_for("job_result", job_id=job_id),
        initial_status=payload,
    )


@app.get("/jobs/<job_id>/status")
def job_status(job_id: str):
    try:
        payload = serialize_job_record(load_job_record(job_id))
    except FileNotFoundError:
        abort(404)
    return payload


@app.get("/jobs/<job_id>/result")
def job_result(job_id: str):
    try:
        payload = load_job_record(job_id)
    except FileNotFoundError:
        abort(404)

    if payload.get("status") != "completed" or not payload.get("artifact_name"):
        return redirect(url_for("job_detail", job_id=job_id))

    tool = get_tool_definition(payload["tool_key"])
    if tool is None:
        abort(404)

    try:
        artifact = resolve_job_artifact(job_id, payload["artifact_name"])
    except FileNotFoundError:
        abort(404)

    return render_result_page(job_id, tool, payload, artifact)


@app.get("/health")
def health():
    return {"status": "ok", "tools": len(TOOL_DEFINITIONS), "mode": "desktop" if is_desktop_mode() else "web"}


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
    app.run(debug=debug, host=host, port=port, threaded=True)


if __name__ == "__main__":
    run_development_server()
