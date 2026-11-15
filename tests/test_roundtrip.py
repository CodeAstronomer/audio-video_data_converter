import hashlib
import os

import numpy as np
import pytest

from app import media, rs, stego


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def roundtrip(src, files, tmp_path, password=None, **kw):
    work = tmp_path / "work"
    out = tmp_path / "out"
    work.mkdir(exist_ok=True)
    out.mkdir(exist_ok=True)
    res = stego.encode_medium(str(src), os.path.basename(src), files,
                              stego.EncodeOptions(password=password, **kw), str(work))
    dec = stego.decode_medium(res.path, password, str(work), str(out))
    assert len(dec.files) == len(files)
    for (name, path), r, e in zip(files, dec.files, dec.manifest["files"]):
        assert r["valid"], r
        assert e["name"] == name
        assert e["sha256"] == sha(path)
        assert sha(r["path"]) == sha(path)
    return res, dec


@pytest.mark.parametrize("password", [None, "Andromeda-M31"])
@pytest.mark.parametrize("use_rs", [False, True])
@pytest.mark.parametrize("src", ["video_audio.mp4", "video.mp4", "audio.wav"])
def test_roundtrip(media_dir, payload_files, tmp_path, src, password, use_rs):
    res, dec = roundtrip(media_dir / src, payload_files, tmp_path, password, use_rs=use_rs)
    assert dec.pub["seed_mode"] == ("password" if password else "fixed")
    out_info = media.probe(res.path, count_frames=False)
    if src.startswith("video"):
        assert res.filename.endswith(".mkv")
        assert out_info.has_video
        assert out_info.has_audio == (src == "video_audio.mp4")
    else:
        assert res.filename.endswith(".flac")
        assert not out_info.has_video


def test_file_spans_video_and_audio(media_dir, tmp_path):
    p = tmp_path / "big.bin"
    p.write_bytes(os.urandom(150_000))
    res, dec = roundtrip(media_dir / "video_audio.mp4", [("big.bin", str(p))], tmp_path, "pw")
    e = dec.manifest["files"][0]
    assert e["frames"] and e["audio"], "file should be distributed over picture and sound"


@pytest.mark.parametrize("codec", ["h264"])
def test_h264_lossless(media_dir, payload_files, tmp_path, codec):
    roundtrip(media_dir / "video.mp4", payload_files, tmp_path, "x", video_codec=codec)


def test_wav_output(media_dir, payload_files, tmp_path):
    res, _ = roundtrip(media_dir / "short.flac", payload_files[1:], tmp_path, None,
                       audio_format="wav", bits=4)
    assert res.filename.endswith(".wav")


def test_auto_escalation(media_dir, tmp_path):
    p = tmp_path / "noise.bin"
    p.write_bytes(os.urandom(400_000))  # incompressible
    res, _ = roundtrip(media_dir / "video.mp4", [("noise.bin", str(p))], tmp_path, None, k=1, bits=1)
    assert res.report["auto_adjusted"]
    assert res.report["k"] > 1 or res.report["bits"] > 1


def test_capacity_error(media_dir, tmp_path):
    p = tmp_path / "huge.bin"
    p.write_bytes(os.urandom(3_000_000))
    with pytest.raises(stego.CapacityError) as ei:
        stego.encode_medium(str(media_dir / "short.flac"), "short.flac", [("huge.bin", str(p))],
                            stego.EncodeOptions(), str(tmp_path))
    assert ei.value.available < ei.value.needed


def test_wrong_and_missing_password(media_dir, payload_files, tmp_path):
    res = stego.encode_medium(str(media_dir / "audio.wav"), "audio.wav", payload_files,
                              stego.EncodeOptions(password="right"), str(tmp_path))
    out = tmp_path / "o"
    out.mkdir()
    with pytest.raises(stego.PasswordRequired):
        stego.decode_medium(res.path, None, str(tmp_path), str(out))
    with pytest.raises(stego.StegoError, match="wrong password"):
        stego.decode_medium(res.path, "wrong", str(tmp_path), str(out))


def test_plain_medium_has_no_data(media_dir, tmp_path):
    with pytest.raises(stego.StegoError, match="no AVDC data"):
        stego.decode_medium(str(media_dir / "audio.wav"), None, str(tmp_path), str(tmp_path))


def test_lsb_changes_are_small(media_dir, payload_files, tmp_path):
    """Only the low bits of selected frames change; other frames stay identical."""
    res = stego.encode_medium(str(media_dir / "video.mp4"), "video.mp4", payload_files,
                              stego.EncodeOptions(bits=2), str(tmp_path))
    info = media.probe(str(media_dir / "video.mp4"))
    a = media.FrameReader(str(media_dir / "video.mp4"), info.width, info.height, str(tmp_path / "a.log"))
    b = media.FrameReader(res.path, info.width, info.height, str(tmp_path / "b.log"))
    changed = 0
    try:
        while (fa := a.read()) is not None:
            fb = b.read()
            da = np.frombuffer(fa, np.uint8).astype(int) - np.frombuffer(fb, np.uint8).astype(int)
            assert np.abs(da).max() <= 3
            changed += bool(np.any(da))
    finally:
        a.close()
        b.close()
    assert 1 <= changed <= info.n_frames // 2


def test_rs_corrects_errors():
    data = os.urandom(10_000)
    enc = bytearray(rs.encode(data))
    for i in range(0, len(enc), 255):
        for j in range(16):  # 16 byte errors per codeword = maximum
            enc[i + j * 7] ^= 0xA5
    out, n = rs.decode(bytes(enc), len(data))
    assert out == data
    assert n == len(enc) // 255


def test_rs_matches_reedsolo():
    import reedsolo

    data = os.urandom(223 * 3)
    ref = b"".join(bytes(reedsolo.RSCodec(32).encode(bytearray(data[i:i + 223])))
                   for i in range(0, len(data), 223))
    assert rs.encode(data) == ref
