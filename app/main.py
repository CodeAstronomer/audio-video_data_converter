"""FastAPI application: upload, encode, decode, download — nothing is persisted."""
from __future__ import annotations

import logging
import os
import re
import secrets
import shutil
import tempfile
import threading
import time
import unicodedata
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from urllib.parse import quote

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask

from . import media, stego

log = logging.getLogger("avdc")
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "2048"))
MAX_UPLOAD = MAX_UPLOAD_MB * 1024 * 1024
JOB_TTL = int(os.environ.get("JOB_TTL_MIN", "30")) * 60
WORK_ROOT = os.environ.get("WORK_DIR", os.path.join(tempfile.gettempdir(), "avdc"))
MAX_PARALLEL = int(os.environ.get("MAX_PARALLEL_JOBS", "2"))
STATIC = os.path.join(os.path.dirname(__file__), "static")

app = FastAPI(title="Audio/Video Data Converter", docs_url=None, redoc_url=None)
_heavy = threading.Semaphore(MAX_PARALLEL)


# ============================================================================ jobs
@dataclass
class Job:
    id: str
    kind: str
    dir: str
    created: float = field(default_factory=time.time)
    touched: float = field(default_factory=time.time)
    status: str = "ready"  # ready | running | done | error
    stage: str = ""
    progress: float = 0.0
    error: dict | None = None
    data: dict = field(default_factory=dict)


class JobStore:
    def __init__(self):
        self.jobs: dict[str, Job] = {}
        self.lock = threading.Lock()

    def create(self, kind: str) -> Job:
        jid = secrets.token_urlsafe(18)
        d = os.path.join(WORK_ROOT, jid)
        os.makedirs(d, mode=0o700)
        job = Job(jid, kind, d)
        with self.lock:
            self.jobs[jid] = job
        return job

    def get(self, jid: str, kind: str | None = None) -> Job:
        with self.lock:
            job = self.jobs.get(jid)
        if not job or (kind and job.kind != kind):
            raise HTTPException(404, detail={"code": "not_found", "message": "unknown or expired job"})
        job.touched = time.time()
        return job

    def delete(self, jid: str) -> None:
        with self.lock:
            job = self.jobs.pop(jid, None)
        if job:
            shutil.rmtree(job.dir, ignore_errors=True)

    def sweep(self) -> None:
        now = time.time()
        with self.lock:
            old = [j.id for j in self.jobs.values()
                   if j.status != "running" and now - j.touched > JOB_TTL]
        for jid in old:
            self.delete(jid)


jobs = JobStore()


def _sweeper():
    while True:
        time.sleep(60)
        try:
            jobs.sweep()
        except Exception:  # pragma: no cover
            log.exception("sweep failed")


@asynccontextmanager
async def lifespan(_app):
    shutil.rmtree(WORK_ROOT, ignore_errors=True)
    os.makedirs(WORK_ROOT, mode=0o700, exist_ok=True)
    threading.Thread(target=_sweeper, daemon=True).start()
    yield
    shutil.rmtree(WORK_ROOT, ignore_errors=True)


app.router.lifespan_context = lifespan


# ============================================================================ helpers
@app.middleware("http")
async def limit_upload(request: Request, call_next):
    cl = request.headers.get("content-length")
    if request.method == "POST" and cl and cl.isdigit() and int(cl) > MAX_UPLOAD:
        return JSONResponse(status_code=413, content={"detail": {
            "code": "too_large", "message": f"upload exceeds {MAX_UPLOAD_MB} MB"}})
    return await call_next(request)


def _err(status: int, code: str, message: str, **extra):
    return HTTPException(status, detail={"code": code, "message": message, **extra})


def safe_name(name: str | None, fallback: str = "file") -> str:
    name = unicodedata.normalize("NFC", name or "")
    name = name.replace("\\", "/").split("/")[-1]
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip().strip(".")
    return name[:200] or fallback


def _save_upload(uf: UploadFile, path: str) -> int:
    total = 0
    with open(path, "wb") as out:
        while True:
            buf = uf.file.read(4 * 1024 * 1024)
            if not buf:
                break
            total += len(buf)
            if total > MAX_UPLOAD:
                raise _err(413, "too_large", f"upload exceeds {MAX_UPLOAD_MB} MB")
            out.write(buf)
    uf.file.close()
    return total


def _content_disposition(name: str) -> str:
    ascii_name = name.encode("ascii", "replace").decode().replace('"', "'").replace("?", "_")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name)}"


def _map_error(e: Exception) -> dict:
    if isinstance(e, stego.CapacityError):
        return {"code": "capacity", "message": str(e), "needed": e.needed, "available": e.available}
    if isinstance(e, stego.PasswordRequired):
        return {"code": "password_required", "message": str(e)}
    if isinstance(e, stego.StegoError) and "wrong password" in str(e):
        return {"code": "wrong_password", "message": str(e)}
    if isinstance(e, stego.StegoError) and "no AVDC data" in str(e):
        return {"code": "no_data", "message": str(e)}
    if isinstance(e, (stego.StegoError, media.MediaError)):
        return {"code": "invalid", "message": str(e)}
    log.exception("internal error")
    return {"code": "internal", "message": f"internal error: {e}"}


def _run_job(job: Job, fn):
    def progress(stage: str, frac: float):
        job.stage, job.progress = stage, max(0.0, min(1.0, frac))
        job.touched = time.time()

    def target():
        with _heavy:
            job.status = "running"
            try:
                fn(progress)
                job.status = "done"
            except Exception as e:  # noqa: BLE001
                job.error = _map_error(e)
                job.status = "error"
            finally:
                job.touched = time.time()

    job.status = "running"
    threading.Thread(target=target, daemon=True).start()


# ============================================================================ API
@app.get("/api/config")
def config():
    return {"max_upload_mb": MAX_UPLOAD_MB, "job_ttl_min": JOB_TTL // 60,
            "video_codecs": list(media.VIDEO_CODECS)}


@app.post("/api/probe")
def probe(medium: UploadFile = File(...)):
    job = jobs.create("encode")
    try:
        name = safe_name(medium.filename, "medium")
        path = os.path.join(job.dir, "source" + os.path.splitext(name)[1][:10])
        _save_upload(medium, path)
        info = media.probe(path)
    except HTTPException:
        jobs.delete(job.id)
        raise
    except media.MediaError as e:
        jobs.delete(job.id)
        raise _err(400, "invalid_media", str(e))
    job.data.update(source=path, source_name=name, info=info)
    return {"token": job.id, "name": name, "info": info.to_dict(),
            "capacity": stego.capacity_report(info, 2, 1)}


@app.get("/api/capacity")
def capacity(token: str, bits: int = 2, k: int = 1):
    job = jobs.get(token, "encode")
    if "info" not in job.data:
        raise _err(409, "invalid", "medium no longer available")
    bits = max(1, min(4, bits))
    return stego.capacity_report(job.data["info"], bits, max(1, k))


@app.post("/api/encode")
def encode(token: str = Form(...), files: list[UploadFile] = File(...),
           password: str = Form(""), k: int = Form(1), bits: int = Form(2),
           rs: bool = Form(False), video_codec: str = Form("ffv1"),
           audio_format: str = Form("flac")):
    job = jobs.get(token, "encode")
    if job.status != "ready" or "source" not in job.data:
        raise _err(409, "invalid", "job already used; upload the medium again")
    if not 1 <= bits <= 4:
        raise _err(400, "invalid", "bits must be 1..4")
    if video_codec not in media.VIDEO_CODECS or audio_format not in ("flac", "wav"):
        raise _err(400, "invalid", "unknown output format")
    in_dir = os.path.join(job.dir, "in")
    os.makedirs(in_dir)
    saved = []
    try:
        for i, uf in enumerate(files):
            name = safe_name(uf.filename, f"file{i}")
            p = os.path.join(in_dir, f"{i:05d}")
            _save_upload(uf, p)
            saved.append((name, p))
    except HTTPException:
        jobs.delete(job.id)
        raise
    if not saved:
        raise _err(400, "invalid", "no files")
    opt = stego.EncodeOptions(password=password or None, k=k, bits=bits, use_rs=rs,
                              video_codec=video_codec, audio_format=audio_format)
    work = os.path.join(job.dir, "work")
    os.makedirs(work)

    def run(progress):
        try:
            res = stego.encode_medium(job.data["source"], job.data["source_name"], saved, opt,
                                      work, progress)
            final = os.path.join(job.dir, "result")
            os.replace(res.path, final)
            job.data.update(result=final, filename=res.filename, report=res.report)
        finally:
            # inputs are not needed any more -> delete immediately
            for p in [job.data.get("source")] + [p for _, p in saved]:
                if p and os.path.exists(p):
                    os.remove(p)
            job.data.pop("source", None)
            shutil.rmtree(in_dir, ignore_errors=True)
            shutil.rmtree(work, ignore_errors=True)

    _run_job(job, run)
    return {"job": job.id}


@app.post("/api/decode")
def decode(medium: UploadFile = File(...), password: str = Form("")):
    job = jobs.create("decode")
    try:
        name = safe_name(medium.filename, "medium")
        src = os.path.join(job.dir, "source" + os.path.splitext(name)[1][:10])
        _save_upload(medium, src)
    except HTTPException:
        jobs.delete(job.id)
        raise
    out_dir = os.path.join(job.dir, "out")
    work = os.path.join(job.dir, "work")
    os.makedirs(out_dir)
    os.makedirs(work)

    def run(progress):
        try:
            res = stego.decode_medium(src, password or None, work, out_dir, progress)
        finally:
            os.remove(src)
            shutil.rmtree(work, ignore_errors=True)
        files = []
        for e, r in zip(res.manifest["files"], res.files):
            files.append({
                "index": r["index"], "name": e["name"], "size": e["size"], "sha256": e["sha256"],
                "sha256_actual": r.get("sha256_actual"), "valid": r["valid"],
                "error": r.get("error"), "stored_len": e["stored_len"], "offset": e["offset"],
                "rs_corrected_blocks": r.get("rs_corrected_blocks", 0),
                "frames": e["frames"], "audio": e["audio"], "available": bool(r.get("path")),
            })
            if r.get("path"):
                job.data.setdefault("paths", {})[r["index"]] = (r["path"], safe_name(e["name"]))
        pub = {k: v for k, v in res.pub.items() if k != "kdf"}
        if res.pub.get("kdf"):
            pub["kdf"] = {k: v for k, v in res.pub["kdf"].items() if k != "salt"}
        job.data["result"] = {"source": res.manifest.get("source"), "params": pub, "files": files,
                              "timeline": res.timeline, "header": res.header}

    _run_job(job, run)
    return {"job": job.id}


@app.get("/api/job/{jid}")
def job_status(jid: str):
    job = jobs.get(jid)
    out = {"status": job.status, "stage": job.stage, "progress": job.progress, "kind": job.kind}
    if job.status == "error":
        out["error"] = job.error
        jobs.delete(jid)  # nothing left worth keeping
    elif job.status == "done":
        if job.kind == "encode":
            out.update(filename=job.data.get("filename"), report=job.data.get("report"),
                       download=f"/api/result/{jid}")
        else:
            out["result"] = job.data.get("result")
    return out


@app.get("/api/result/{jid}")
def download_result(jid: str):
    job = jobs.get(jid, "encode")
    path = job.data.get("result")
    if job.status != "done" or not path or not os.path.exists(path):
        raise _err(404, "not_found", "result not available (already downloaded?)")
    media_type = "audio/wav" if path and job.data["filename"].endswith(".wav") else (
        "audio/flac" if job.data["filename"].endswith(".flac") else "video/x-matroska")
    return FileResponse(path, media_type=media_type,
                        headers={"Content-Disposition": _content_disposition(job.data["filename"])},
                        background=BackgroundTask(jobs.delete, jid))


@app.get("/api/extract/{jid}/{index}")
def download_file(jid: str, index: int):
    job = jobs.get(jid, "decode")
    paths = job.data.get("paths", {})
    if index not in paths or not os.path.exists(paths[index][0]):
        raise _err(404, "not_found", "file not available (already downloaded?)")
    path, name = paths[index]

    def cleanup():
        if os.path.exists(path):
            os.remove(path)
        paths.pop(index, None)
        if not paths:
            jobs.delete(jid)

    return FileResponse(path, media_type="application/octet-stream",
                        headers={"Content-Disposition": _content_disposition(name)},
                        background=BackgroundTask(cleanup))


@app.delete("/api/job/{jid}")
def delete_job(jid: str):
    with jobs.lock:
        job = jobs.jobs.get(jid)
    if job and job.status != "running":
        jobs.delete(jid)
    return {"ok": True}


app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
