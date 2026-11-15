"""Carrier planning, header format and LSB embedding / extraction.

Carrier model
-------------
The medium is split into *segments*:

* video: one segment per selected video frame (all R, G, B values of the
  frame, ``bits`` LSBs each),
* audio: one segment per 1-second block of PCM samples (all channels,
  ``bits`` LSBs of every 16-bit sample).

Data segments are ordered chronologically and filled one after another with
the payload stream, so a file can span video frames *and* audio blocks.
Inside every segment the sample positions are a pseudo-random permutation
seeded from the password (or a fixed seed).

The header lives in the first segments of the medium (video frames 0.. or,
for pure audio, the first 1-second audio blocks) and is written with a
fixed seed and 2 bits so the decoder can always find it.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import struct
import zlib
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Callable

import numpy as np
import zstandard as zstd

from . import media, payload, rs

MAGIC = b"AVDC"
VERSION = 1
PREFIX_LEN = 16
HEADER_BITS = 2
HEADER_SEED = 0x48454144_45525F31  # "HEADER_1"
HEADER_MAX_SECONDS = 2

FLAG_ENCRYPTED = 1
FLAG_RS = 2
FLAG_VIDEO = 4
FLAG_AUDIO = 8

TAG_V, TAG_A, TAG_HV, TAG_HA, TAG_SEL = 1, 2, 3, 4, 5
MASK64 = (1 << 64) - 1


class StegoError(Exception):
    pass


class CapacityError(StegoError):
    def __init__(self, needed: int, available: int):
        super().__init__(f"payload needs {needed} bytes, maximum capacity is {available} bytes")
        self.needed = needed
        self.available = available


class PasswordRequired(StegoError):
    pass


# ============================================================================ plan
@dataclass
class Layout:
    has_video: bool
    width: int
    height: int
    fps: Fraction
    n_frames: int
    has_audio: bool
    rate: int
    channels: int
    n_samples: int
    bits: int
    k: int  # carrier frames per second
    hdr_segs: int = 1

    @property
    def frame_vals(self) -> int:
        return self.width * self.height * 3

    @property
    def n_blocks(self) -> int:
        return -(-self.n_samples // self.rate) if self.has_audio and self.rate else 0

    def block_range(self, j: int) -> tuple[int, int]:
        return j * self.rate, min((j + 1) * self.rate, self.n_samples)

    def header_in_video(self) -> bool:
        return self.has_video

    def header_seg_caps(self) -> list[int]:
        """Capacity (bytes) of every *possible* header segment, in order."""
        if self.has_video:
            n = min(self.n_frames, math.ceil(HEADER_MAX_SECONDS * self.fps))
            return [self.frame_vals * HEADER_BITS // 8] * n
        caps = []
        for j in range(min(HEADER_MAX_SECONDS, self.n_blocks)):
            a, b = self.block_range(j)
            caps.append((b - a) * self.channels * HEADER_BITS // 8)
        return caps

    def to_pub(self) -> dict:
        return {
            "video": {"w": self.width, "h": self.height, "fps": [self.fps.numerator, self.fps.denominator],
                      "frames": self.n_frames} if self.has_video else None,
            "audio": {"rate": self.rate, "ch": self.channels, "samples": self.n_samples}
            if self.has_audio else None,
            "bits": self.bits, "k": self.k, "hdr_segs": self.hdr_segs,
        }

    @classmethod
    def from_pub(cls, p: dict) -> "Layout":
        v, a = p.get("video"), p.get("audio")
        return cls(
            has_video=bool(v), width=v["w"] if v else 0, height=v["h"] if v else 0,
            fps=Fraction(*v["fps"]) if v else Fraction(0), n_frames=v["frames"] if v else 0,
            has_audio=bool(a), rate=a["rate"] if a else 0, channels=a["ch"] if a else 0,
            n_samples=a["samples"] if a else 0, bits=p["bits"], k=p["k"], hdr_segs=p["hdr_segs"])


def _windows(lay: Layout):
    """Yield (second, first_frame, end_frame) windows of the video."""
    num, den = lay.fps.numerator, lay.fps.denominator
    s = 0
    while True:
        start = -((-s * num) // den)
        if start >= lay.n_frames:
            return
        end = min(-((-(s + 1) * num) // den), lay.n_frames)
        yield s, start, end
        s += 1


def selected_frames(lay: Layout, seed: int) -> list[int]:
    out: list[int] = []
    first = lay.hdr_segs if lay.has_video else 0
    for s, a, b in _windows(lay):
        a = max(a, first)
        n = b - a
        if n <= 0:
            continue
        if lay.k >= n:
            out.extend(range(a, b))
        else:
            rng = np.random.default_rng([seed & MASK64, TAG_SEL, s])
            pick = np.sort(rng.choice(n, lay.k, replace=False))
            out.extend(int(a + x) for x in pick)
    return out


def count_selected_frames(lay: Layout) -> int:
    first = lay.hdr_segs if lay.has_video else 0
    return sum(min(lay.k, b - max(a, first)) for _, a, b in _windows(lay) if b > max(a, first))


@dataclass
class Seg:
    time: float
    kind: str  # "v" | "a"
    idx: int
    cap: int  # bytes
    offset: int = 0  # stream offset
    nbytes: int = 0  # bytes actually stored


def data_segments(lay: Layout, seed: int) -> list[Seg]:
    segs: list[Seg] = []
    if lay.has_video:
        cap = lay.frame_vals * lay.bits // 8
        fps = float(lay.fps)
        segs += [Seg(i / fps, "v", i, cap) for i in selected_frames(lay, seed)]
    if lay.has_audio:
        first = 0 if lay.has_video else lay.hdr_segs
        for j in range(first, lay.n_blocks):
            a, b = lay.block_range(j)
            segs.append(Seg(float(j), "a", j, (b - a) * lay.channels * lay.bits // 8))
    segs.sort(key=lambda s: (s.time, s.kind != "a"))
    return segs


def capacity(lay: Layout) -> dict:
    """Data capacity in bytes (excluding header segments)."""
    v = count_selected_frames(lay) * (lay.frame_vals * lay.bits // 8) if lay.has_video else 0
    a = 0
    if lay.has_audio:
        first = 0 if lay.has_video else lay.hdr_segs
        full = lay.rate * lay.channels * lay.bits // 8
        for j in range(first, lay.n_blocks):
            x, y = lay.block_range(j)
            a += full if y - x == lay.rate else (y - x) * lay.channels * lay.bits // 8
    return {"video": v, "audio": a, "total": v + a}


def assign(segs: list[Seg], stream_len: int) -> list[Seg]:
    pos = 0
    used = []
    for s in segs:
        if pos >= stream_len:
            break
        s.offset = pos
        s.nbytes = min(s.cap, stream_len - pos)
        pos += s.nbytes
        used.append(s)
    if pos < stream_len:
        raise CapacityError(stream_len, pos)
    return used


def k_candidates(fps: Fraction, k0: int) -> list[int]:
    kmax = max(1, math.ceil(fps))
    ks = sorted({k for k in (k0, 2, 3, 5, 10, 15, 24, 30, 60) if k0 <= k < kmax} | {kmax})
    return [k for k in ks if k >= min(k0, kmax)]


# ============================================================================ bits
def _syms_from_bytes(data: bytes, bits: int) -> np.ndarray:
    b = np.unpackbits(np.frombuffer(data, dtype=np.uint8))
    pad = (-len(b)) % bits
    if pad:
        b = np.concatenate([b, np.zeros(pad, dtype=np.uint8)])
    b = b.reshape(-1, bits)
    w = (1 << np.arange(bits - 1, -1, -1)).astype(np.uint8)
    return (b * w).sum(axis=1).astype(np.uint8)


def _bytes_from_syms(syms: np.ndarray, nbytes: int, bits: int) -> bytes:
    shifts = np.arange(bits - 1, -1, -1, dtype=np.uint8)
    b = ((syms.astype(np.uint8)[:, None] >> shifts) & 1).astype(np.uint8).reshape(-1)
    return np.packbits(b[: nbytes * 8]).tobytes()


def _perm(n: int, seed: int, tag: int, idx: int, take: int) -> np.ndarray:
    rng = np.random.default_rng([seed & MASK64, tag, idx])
    return rng.permutation(n)[:take]


def embed(values: np.ndarray, data: bytes, bits: int, seed: int, tag: int, idx: int) -> None:
    if not data:
        return
    nsym = -(-len(data) * 8 // bits)
    if nsym > values.size:
        raise StegoError("segment overflow")
    pos = _perm(values.size, seed, tag, idx, nsym)
    syms = _syms_from_bytes(data, bits).astype(values.dtype)
    keep = values.dtype.type(~((1 << bits) - 1) & np.iinfo(values.dtype).max)
    values[pos] = (values[pos] & keep) | syms


def extract(values: np.ndarray, nbytes: int, bits: int, seed: int, tag: int, idx: int) -> bytes:
    if nbytes <= 0:
        return b""
    nsym = -(-nbytes * 8 // bits)
    pos = _perm(values.size, seed, tag, idx, nsym)
    syms = (values[pos] & ((1 << bits) - 1)).astype(np.uint8)
    return _bytes_from_syms(syms, nbytes, bits)


# ============================================================================ header
def build_header(flags: int, pub: dict, manifest: dict, enc_key: bytes | None) -> bytes:
    pub_b = json.dumps(pub, separators=(",", ":")).encode()
    man_b = zstd.ZstdCompressor(level=19).compress(json.dumps(manifest, separators=(",", ":")).encode())
    if enc_key:
        man_b = payload.encrypt_blob(enc_key, man_b, b"avdc-manifest")
    raw = struct.pack(">I", len(pub_b)) + pub_b + struct.pack(">I", len(man_b)) + man_b
    raw += hashlib.sha256(raw).digest()
    body = rs.encode(raw) if flags & FLAG_RS else raw
    pre = MAGIC + struct.pack(">BBHI", VERSION, flags, 0, len(body))
    pre += struct.pack(">I", zlib.crc32(pre))
    return pre + body


def parse_prefix(pre: bytes) -> tuple[int, int]:
    if len(pre) < PREFIX_LEN or pre[:4] != MAGIC:
        raise StegoError("no AVDC data found in this medium")
    if struct.unpack(">I", pre[12:16])[0] != zlib.crc32(pre[:12]):
        raise StegoError("header prefix checksum mismatch")
    ver, flags, _, body_len = struct.unpack(">BBHI", pre[4:12])
    if ver != VERSION:
        raise StegoError(f"unsupported format version {ver}")
    return flags, body_len


def parse_body(flags: int, body: bytes) -> tuple[dict, bytes, dict]:
    info = {"rs_corrected_blocks": 0}
    if flags & FLAG_RS:
        try:
            raw, info["rs_corrected_blocks"] = rs.decode(body, len(body) // rs.N * rs.K)
        except rs.RSDecodeError as e:
            raise StegoError(f"header damaged: {e}") from e
    else:
        raw = body
    try:
        pl = struct.unpack(">I", raw[:4])[0]
        pub_b = raw[4 : 4 + pl]
        ml = struct.unpack(">I", raw[4 + pl : 8 + pl])[0]
        man_b = raw[8 + pl : 8 + pl + ml]
        end = 8 + pl + ml
        digest = raw[end : end + 32]
    except struct.error as e:
        raise StegoError("header truncated") from e
    if hashlib.sha256(raw[:end]).digest() != digest:
        raise StegoError("header checksum (SHA-256) mismatch")
    info["header_sha256"] = digest.hex()
    return json.loads(pub_b), man_b, info


def open_manifest(man_b: bytes, enc_key: bytes | None) -> dict:
    if enc_key:
        man_b = payload.decrypt_blob(enc_key, man_b, b"avdc-manifest")
    return json.loads(zstd.ZstdDecompressor().decompress(man_b))


# ============================================================================ helpers
def _merge_ranges(rngs: list[list[int]]) -> list[list[int]]:
    out: list[list[int]] = []
    for a, b in rngs:
        if out and out[-1][1] == a:
            out[-1][1] = b
        else:
            out.append([a, b])
    return out


def file_positions(used: list[Seg], lay: Layout, off: int, length: int) -> dict:
    frames, audio = [], []
    end = off + length
    for s in used:
        if s.offset < end and s.offset + s.nbytes > off and s.nbytes:
            if s.kind == "v":
                frames.append(s.idx)
            else:
                a, b = lay.block_range(s.idx)
                audio.append([a, b])
    return {"frames": frames, "audio": _merge_ranges(audio)}


def layout_from_info(info: media.MediaInfo, bits: int, k: int, n_samples: int | None = None) -> Layout:
    return Layout(
        has_video=info.has_video, width=info.width, height=info.height, fps=info.fps,
        n_frames=info.n_frames, has_audio=info.has_audio and (n_samples if n_samples is not None
                                                              else info.n_samples) > 0,
        rate=info.sample_rate, channels=info.channels,
        n_samples=n_samples if n_samples is not None else info.n_samples, bits=bits, k=k)


def capacity_report(info: media.MediaInfo, bits: int, k: int) -> dict:
    lay = layout_from_info(info, bits, k)
    cur = capacity(lay)
    mx = capacity(layout_from_info(info, 4, max(1, math.ceil(info.fps)) if info.has_video else 1))
    return {
        "bits": bits, "k": k, "video_bytes": cur["video"], "audio_bytes": cur["audio"],
        "total_bytes": cur["total"], "max_total_bytes": mx["total"],
        "frame_bytes": lay.frame_vals * bits // 8 if lay.has_video else 0,
        "carrier_frames": count_selected_frames(lay) if lay.has_video else 0,
        "header_bytes_max": sum(lay.header_seg_caps()),
    }


# ============================================================================ encode
@dataclass
class EncodeOptions:
    password: str | None = None
    k: int = 1
    bits: int = 2
    use_rs: bool = False
    video_codec: str = "ffv1"
    audio_format: str = "flac"  # for audio-only output: flac | wav


@dataclass
class EncodeResult:
    path: str
    filename: str
    report: dict = field(default_factory=dict)


Progress = Callable[[str, float], None]


def _noop(stage: str, frac: float) -> None:
    pass


def encode_medium(src: str, src_name: str, files: list[tuple[str, str]], opt: EncodeOptions,
                  work: str, progress: Progress = _noop) -> EncodeResult:
    if not files:
        raise StegoError("no files to embed")
    if not 1 <= opt.bits <= 4:
        raise StegoError("bits must be 1..4")
    info = media.probe(src)
    progress("payload", 0.0)

    # ---------------------------------------------------------------- keys
    salt = os.urandom(16) if opt.password else None
    kdf = payload.default_kdf() if opt.password else None
    keys = payload.make_keys(opt.password, salt, kdf)
    flags = (FLAG_ENCRYPTED if opt.password else 0) | (FLAG_RS if opt.use_rs else 0)

    # ---------------------------------------------------------------- payload stream
    stream_path = os.path.join(work, "payload.bin")
    entries = []
    with open(stream_path, "wb") as out:
        for i, (name, path) in enumerate(files):
            off = out.tell()
            with open(path, "rb") as f:
                e = payload.pack_file(f, out, keys.enc_key, opt.use_rs, i)
            e = {"name": name, **e, "offset": off}
            entries.append(e)
            progress("payload", (i + 1) / len(files))
        stream_len = out.tell()

    # ---------------------------------------------------------------- audio decode
    raw_audio = None
    n_samples = 0
    if info.has_audio:
        raw_audio = os.path.join(work, "audio.raw")
        media.decode_audio_raw(src, raw_audio)
        n_samples = os.path.getsize(raw_audio) // (2 * info.channels)
    progress("plan", 0.0)

    # ---------------------------------------------------------------- choose parameters
    ks = k_candidates(info.fps, max(1, opt.k)) if info.has_video else [1]
    chosen = None
    best_cap = 0
    for bits in range(opt.bits, 5):
        for k in ks:
            lay = layout_from_info(info, bits, k, n_samples)
            if not lay.has_video and not lay.has_audio:
                raise StegoError("medium has no usable carrier")
            hcaps = lay.header_seg_caps()
            if not hcaps:
                raise StegoError("medium too short for the header")
            h = 1
            while True:
                lay.hdr_segs = h
                cap = capacity(lay)["total"]
                best_cap = max(best_cap, cap)
                if cap < stream_len:
                    break
                used = assign(data_segments(lay, keys.seed), stream_len)
                manifest = _manifest(entries, used, lay, src_name)
                hdr = build_header(flags | (FLAG_VIDEO if lay.has_video else 0)
                                   | (FLAG_AUDIO if lay.has_audio else 0),
                                   _pub(lay, stream_len, kdf, salt), manifest, keys.enc_key)
                need = _segs_needed(hcaps, len(hdr))
                if need is None:
                    raise StegoError(
                        f"header ({len(hdr)} bytes) does not fit into the first "
                        f"{HEADER_MAX_SECONDS} s of the medium (max {sum(hcaps)} bytes); "
                        "use fewer files or a larger medium")
                if need <= h:
                    chosen = (lay, used, hdr, manifest)
                    break
                h = need
            if chosen:
                break
        if chosen:
            break
    if not chosen:
        raise CapacityError(stream_len, best_cap)
    lay, used, hdr, manifest = chosen

    stream = np.memmap(stream_path, dtype=np.uint8, mode="r") if stream_len else np.zeros(0, np.uint8)
    base = os.path.splitext(os.path.basename(src_name))[0] or "output"

    # ---------------------------------------------------------------- audio embed
    audio_out = None
    if lay.has_audio:
        progress("audio", 0.0)
        pcm = np.memmap(raw_audio, dtype=np.int16, mode="r+").view(np.uint16)
        ch = lay.channels
        if not lay.has_video:
            _write_header(hdr, lay.header_seg_caps()[: lay.hdr_segs],
                          lambda j: pcm[slice(*[x * ch for x in lay.block_range(j)])], TAG_HA)
        for s in used:
            if s.kind == "a":
                a, b = lay.block_range(s.idx)
                embed(pcm[a * ch : b * ch], stream[s.offset : s.offset + s.nbytes].tobytes(),
                      lay.bits, keys.seed, TAG_A, s.idx)
        pcm.flush()
        del pcm
        if lay.has_video:
            audio_out = os.path.join(work, "audio.flac")
            media.encode_audio_raw(raw_audio, lay.rate, ch, audio_out, "flac")
        else:
            ext = "wav" if opt.audio_format == "wav" else "flac"
            out_path = os.path.join(work, f"result.{ext}")
            media.encode_audio_raw(raw_audio, lay.rate, ch, out_path, ext)
            os.remove(raw_audio)
            return EncodeResult(out_path, f"{base}.avdc.{ext}",
                                _report(lay, used, hdr, stream_len, entries, opt, out_path))
        os.remove(raw_audio)

    # ---------------------------------------------------------------- video embed
    if opt.video_codec not in media.VIDEO_CODECS:
        raise StegoError("unknown video codec")
    out_path = os.path.join(work, "result.mkv")
    vsegs = {s.idx: s for s in used if s.kind == "v"}
    last_needed = max([lay.hdr_segs - 1] + list(vsegs))
    reader = media.FrameReader(src, lay.width, lay.height, os.path.join(work, "dec.log"))
    writer = media.FrameWriter(out_path, lay.width, lay.height, lay.fps, opt.video_codec,
                               audio_out, os.path.join(work, "enc.log"))
    hdr_pos = 0
    hcap = lay.frame_vals * HEADER_BITS // 8
    i = 0
    try:
        while True:
            buf = reader.read()
            if buf is None:
                break
            if i < lay.hdr_segs or i in vsegs:
                frame = np.frombuffer(buf, dtype=np.uint8).copy()
                if i < lay.hdr_segs:
                    chunk = hdr[hdr_pos : hdr_pos + hcap]
                    hdr_pos += len(chunk)
                    embed(frame, chunk, HEADER_BITS, HEADER_SEED, TAG_HV, i)
                else:
                    s = vsegs[i]
                    embed(frame, stream[s.offset : s.offset + s.nbytes].tobytes(),
                          lay.bits, keys.seed, TAG_V, i)
                writer.write(frame.data)
            else:
                writer.write(buf)
            i += 1
            if i % 25 == 0:
                progress("video", min(1.0, i / max(1, lay.n_frames)))
        if i <= last_needed:
            raise StegoError(f"video has only {i} decodable frames, plan needed {last_needed + 1}")
        writer.finish()
    except BaseException:
        writer.abort()
        raise
    finally:
        reader.close()
    if audio_out:
        os.remove(audio_out)
    return EncodeResult(out_path, f"{base}.avdc.mkv",
                        _report(lay, used, hdr, stream_len, entries, opt, out_path))


def _segs_needed(caps: list[int], n: int) -> int | None:
    tot = 0
    for i, c in enumerate(caps):
        tot += c
        if tot >= n:
            return i + 1
    return None


def _pub(lay: Layout, stream_len: int, kdf: dict | None, salt: bytes | None) -> dict:
    return {**lay.to_pub(), "stream_len": stream_len,
            "seed_mode": "password" if kdf else "fixed",
            "kdf": {**kdf, "salt": salt.hex()} if kdf else None,
            "compression": "zstd", "enc": "aes-256-gcm" if kdf else None,
            "rs": f"RS({rs.N},{rs.K})"}


def _manifest(entries: list[dict], used: list[Seg], lay: Layout, src_name: str) -> dict:
    files = []
    for e in entries:
        files.append({**e, **file_positions(used, lay, e["offset"], e["stored_len"])})
    return {"source": os.path.basename(src_name), "files": files}


def _write_header(hdr: bytes, caps: list[int], get_values, tag: int) -> None:
    pos = 0
    for j, c in enumerate(caps):
        chunk = hdr[pos : pos + c]
        pos += len(chunk)
        embed(get_values(j), chunk, HEADER_BITS, HEADER_SEED, tag, j)


def _report(lay, used, hdr, stream_len, entries, opt, out_path) -> dict:
    cap = capacity(lay)
    return {
        "bits": lay.bits, "k": lay.k, "auto_adjusted": lay.bits != opt.bits or (lay.has_video and lay.k != opt.k),
        "requested": {"bits": opt.bits, "k": opt.k},
        "capacity_bytes": cap["total"], "stream_bytes": stream_len,
        "header_bytes": len(hdr), "header_segments": lay.hdr_segs,
        "segments_used": len(used), "output_bytes": os.path.getsize(out_path),
        "files": [{"name": e["name"], "size": e["size"], "stored": e["stored_len"]} for e in entries],
        "encrypted": bool(opt.password), "rs": opt.use_rs,
    }


# ============================================================================ decode
@dataclass
class DecodeResult:
    pub: dict
    manifest: dict
    files: list[dict]
    timeline: dict
    header: dict


def decode_medium(src: str, password: str | None, work: str, out_dir: str,
                  progress: Progress = _noop) -> DecodeResult:
    info = media.probe(src, count_frames=False)
    raw_audio = None
    pcm = None
    reader = None
    try:
        # ------------------------------------------------------------ header
        if info.has_video:
            reader = media.FrameReader(src, info.width, info.height, os.path.join(work, "dec.log"))
            hcap = info.width * info.height * 3 * HEADER_BITS // 8
            max_h = math.ceil(HEADER_MAX_SECONDS * info.fps)
            frames_read = 0

            def next_header_values():
                nonlocal frames_read
                buf = reader.read()
                if buf is None:
                    raise StegoError("video ended inside the header")
                frames_read += 1
                return np.frombuffer(buf, dtype=np.uint8)

            hdr, h = _read_header(lambda j: next_header_values(), [hcap] * max_h, TAG_HV)
        else:
            raw_audio = os.path.join(work, "audio.raw")
            media.decode_audio_raw(src, raw_audio)
            n_samples = os.path.getsize(raw_audio) // (2 * info.channels)
            pcm = np.memmap(raw_audio, dtype=np.int16, mode="r").view(np.uint16)
            tmp = Layout(False, 0, 0, Fraction(0), 0, True, info.sample_rate, info.channels,
                         n_samples, HEADER_BITS, 1)
            ch = info.channels
            hdr, h = _read_header(lambda j: pcm[slice(*[x * ch for x in tmp.block_range(j)])],
                                  tmp.header_seg_caps(), TAG_HA)
        flags, body_len = parse_prefix(hdr[:PREFIX_LEN])
        pub, man_b, hinfo = parse_body(flags, hdr[PREFIX_LEN : PREFIX_LEN + body_len])
        lay = Layout.from_pub(pub)
        if lay.hdr_segs != h:
            raise StegoError("header segment count mismatch")
        if flags & FLAG_ENCRYPTED and not password:
            raise PasswordRequired("this medium is password protected")
        kdf = pub.get("kdf")
        keys = payload.make_keys(password if flags & FLAG_ENCRYPTED else None,
                                 bytes.fromhex(kdf["salt"]) if kdf else None, kdf)
        try:
            manifest = open_manifest(man_b, keys.enc_key)
        except payload.PayloadError as e:
            raise StegoError("wrong password") from e

        # ------------------------------------------------------------ plan
        if lay.has_video and (lay.width, lay.height) != (info.width, info.height):
            raise StegoError("video dimensions differ from header")
        stream_len = pub["stream_len"]
        used = assign(data_segments(lay, keys.seed), stream_len)
        stream_path = os.path.join(work, "stream.bin")
        with open(stream_path, "wb") as f:
            f.truncate(stream_len)
        sf = open(stream_path, "r+b")
        try:
            # -------------------------------------------------------- video
            if lay.has_video:
                vsegs = {s.idx: s for s in used if s.kind == "v"}
                last = max(vsegs) if vsegs else -1
                i = frames_read
                while i <= last:
                    buf = reader.read()
                    if buf is None:
                        raise StegoError(f"video ended at frame {i}, data expected up to frame {last}")
                    s = vsegs.get(i)
                    if s:
                        sf.seek(s.offset)
                        sf.write(extract(np.frombuffer(buf, dtype=np.uint8), s.nbytes, lay.bits,
                                         keys.seed, TAG_V, i))
                    i += 1
                    if i % 25 == 0:
                        progress("video", i / max(1, last + 1))
            # -------------------------------------------------------- audio
            asegs = [s for s in used if s.kind == "a"]
            if asegs:
                if pcm is None:
                    if not info.has_audio:
                        raise StegoError("audio track carrying data is missing")
                    raw_audio = os.path.join(work, "audio.raw")
                    media.decode_audio_raw(src, raw_audio)
                    pcm = np.memmap(raw_audio, dtype=np.int16, mode="r").view(np.uint16)
                if pcm.size // lay.channels < lay.n_samples:
                    raise StegoError("audio track is shorter than recorded in the header")
                ch = lay.channels
                for s in asegs:
                    a, b = lay.block_range(s.idx)
                    sf.seek(s.offset)
                    sf.write(extract(pcm[a * ch : b * ch], s.nbytes, lay.bits, keys.seed, TAG_A, s.idx))
            # -------------------------------------------------------- files
            sf.flush()
            results = []
            use_rs = bool(flags & FLAG_RS)
            for i, e in enumerate(manifest["files"]):
                out_path = os.path.join(out_dir, f"{i:05d}.bin")
                try:
                    with open(out_path, "wb") as fo:
                        r = payload.unpack_file(sf, e, i, keys.enc_key, use_rs, fo)
                except (payload.PayloadError, rs.RSDecodeError) as ex:
                    r = {"valid": False, "error": str(ex), "sha256_actual": None, "size_actual": None}
                    if os.path.exists(out_path):
                        os.remove(out_path)
                results.append({"index": i, "path": out_path if r["valid"] or os.path.exists(out_path) else None,
                                **r})
                progress("files", (i + 1) / len(manifest["files"]))
        finally:
            sf.close()
            os.remove(stream_path)
    finally:
        if reader:
            reader.close()
        if pcm is not None:
            del pcm
        if raw_audio and os.path.exists(raw_audio):
            os.remove(raw_audio)

    timeline = _timeline(lay, h)
    return DecodeResult(pub, manifest, results, timeline,
                        {**hinfo, "flags": flags, "header_bytes": len(hdr[: PREFIX_LEN + body_len])})


def _read_header(get_values, caps: list[int], tag: int) -> tuple[bytes, int]:
    if not caps:
        raise StegoError("medium too short")
    out = bytearray()
    total = None
    for j, c in enumerate(caps):
        vals = get_values(j)
        out += extract(vals, c, HEADER_BITS, HEADER_SEED, tag, j)
        if total is None and len(out) >= PREFIX_LEN:
            _, body_len = parse_prefix(bytes(out[:PREFIX_LEN]))
            total = PREFIX_LEN + body_len
        if total is not None and len(out) >= total:
            return bytes(out[:total]), j + 1
    raise StegoError("header incomplete")


def _timeline(lay: Layout, h: int) -> dict:
    dur_v = lay.n_frames / float(lay.fps) if lay.has_video else 0
    dur_a = lay.n_samples / lay.rate if lay.has_audio else 0
    hdr = ({"frames": list(range(h))} if lay.has_video
           else {"audio": [list(lay.block_range(j)) for j in range(h)]})
    return {"duration": max(dur_v, dur_a), "fps": float(lay.fps) if lay.has_video else 0,
            "rate": lay.rate, "header": hdr}
