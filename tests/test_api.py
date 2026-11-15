import hashlib
import os
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from app import main
    monkeypatch.setattr(main, "WORK_ROOT", str(tmp_path / "work"))
    with TestClient(main.app) as c:
        yield c, main


def wait(c, jid):
    for _ in range(600):
        r = c.get(f"/api/job/{jid}").json()
        if r["status"] in ("done", "error"):
            return r
        time.sleep(0.1)
    raise AssertionError("timeout")


@pytest.mark.parametrize("password", ["", "Sirius"])
def test_api_roundtrip(client, media_dir, payload_files, password):
    c, main = client
    with open(media_dir / "video_audio.mp4", "rb") as f:
        r = c.post("/api/probe", files={"medium": ("clip.mp4", f, "video/mp4")})
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    assert r.json()["capacity"]["total_bytes"] > 0
    cap = c.get("/api/capacity", params={"token": token, "bits": 3, "k": 2}).json()
    assert cap["bits"] == 3 and cap["k"] == 2

    files = [("files", (n, open(p, "rb"))) for n, p in payload_files]
    r = c.post("/api/encode", data={"token": token, "password": password, "bits": 2, "k": 1, "rs": "true"},
               files=files)
    assert r.status_code == 200, r.text
    st = wait(c, r.json()["job"])
    assert st["status"] == "done", st
    out = c.get(st["download"])
    assert out.status_code == 200
    # result is deleted after the download
    assert c.get(st["download"]).status_code == 404
    assert not os.path.exists(os.path.join(main.WORK_ROOT, token))

    r = c.post("/api/decode", files={"medium": ("clip.avdc.mkv", out.content, "video/x-matroska")},
               data={"password": password})
    st = wait(c, r.json()["job"])
    assert st["status"] == "done", st
    res = st["result"]
    jid = r.json()["job"]
    assert len(res["files"]) == len(payload_files)
    for f, (name, path) in zip(res["files"], payload_files):
        assert f["valid"] and f["name"] == name
        body = c.get(f"/api/extract/{jid}/{f['index']}")
        assert body.status_code == 200
        assert hashlib.sha256(body.content).hexdigest() == f["sha256"]
    # everything downloaded -> job directory removed
    assert not os.path.exists(os.path.join(main.WORK_ROOT, jid))


def test_api_password_required(client, media_dir, payload_files):
    c, _ = client
    with open(media_dir / "audio.wav", "rb") as f:
        token = c.post("/api/probe", files={"medium": ("a.wav", f)}).json()["token"]
    r = c.post("/api/encode", data={"token": token, "password": "pw"},
               files=[("files", (n, open(p, "rb"))) for n, p in payload_files])
    st = wait(c, r.json()["job"])
    out = c.get(st["download"]).content
    r = c.post("/api/decode", files={"medium": ("a.flac", out)})
    st = wait(c, r.json()["job"])
    assert st["status"] == "error" and st["error"]["code"] == "password_required"


def test_upload_limit(client, monkeypatch):
    c, main = client
    monkeypatch.setattr(main, "MAX_UPLOAD", 1000)
    r = c.post("/api/probe", files={"medium": ("x.wav", b"\0" * 5000)})
    assert r.status_code == 413
