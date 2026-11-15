"""Payload pipeline: files -> zstd -> (AES-256-GCM) -> (Reed-Solomon).

Every file is processed into its own contiguous blob inside one payload
stream, so the manifest can tell exactly which carrier segments hold which
file and every file can be restored and verified independently.
"""
from __future__ import annotations

import hashlib
import os
import struct
from dataclasses import dataclass
from typing import BinaryIO

import zstandard as zstd
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from . import rs

ENC_CHUNK = 16 * 1024 * 1024  # plaintext bytes per GCM chunk
GCM_TAG = 16
IO_CHUNK = 4 * 1024 * 1024
FIXED_SEED = 0x41564443_2D534545  # "AVDC-SEE"

KDF_ARGON2 = {"name": "argon2id", "t": 3, "m": 65536, "p": 4}
KDF_PBKDF2 = {"name": "pbkdf2-sha256", "iter": 600_000}


class PayloadError(Exception):
    pass


# --------------------------------------------------------------------------- keys
def default_kdf() -> dict:
    try:
        import argon2.low_level  # noqa: F401

        return dict(KDF_ARGON2)
    except ImportError:  # pragma: no cover
        return dict(KDF_PBKDF2)


def derive_master(password: str, salt: bytes, kdf: dict) -> bytes:
    pw = password.encode("utf-8")
    if kdf["name"] == "argon2id":
        from argon2.low_level import Type, hash_secret_raw

        return hash_secret_raw(pw, salt, time_cost=kdf["t"], memory_cost=kdf["m"],
                               parallelism=kdf["p"], hash_len=32, type=Type.ID)
    if kdf["name"] == "pbkdf2-sha256":
        return hashlib.pbkdf2_hmac("sha256", pw, salt, kdf["iter"], 32)
    raise PayloadError(f"unknown KDF {kdf['name']}")


@dataclass
class Keys:
    enc_key: bytes | None
    seed: int


def make_keys(password: str | None, salt: bytes | None, kdf: dict | None) -> Keys:
    if not password:
        return Keys(None, FIXED_SEED)
    master = derive_master(password, salt, kdf)
    enc = hashlib.sha256(b"avdc-enc\0" + master).digest()
    seed = int.from_bytes(hashlib.sha256(b"avdc-seed\0" + master).digest()[:8], "big")
    return Keys(enc, seed)


def _chunk_nonce(base: bytes, idx: int) -> bytes:
    return base[:8] + struct.pack(">I", idx)


def encrypt_blob(key: bytes, data: bytes, aad: bytes = b"") -> bytes:
    nonce = os.urandom(12)
    return nonce + AESGCM(key).encrypt(nonce, data, aad)


def decrypt_blob(key: bytes, blob: bytes, aad: bytes = b"") -> bytes:
    from cryptography.exceptions import InvalidTag

    try:
        return AESGCM(key).decrypt(blob[:12], blob[12:], aad)
    except InvalidTag as e:
        raise PayloadError("wrong password or corrupted data") from e


# --------------------------------------------------------------------------- encode
def pack_file(src: BinaryIO, out: BinaryIO, enc_key: bytes | None, use_rs: bool,
              file_index: int) -> dict:
    """Compress/encrypt/RS-encode ``src`` and append it to ``out``.

    Returns the manifest fields describing the stored blob.
    """
    sha = hashlib.sha256()
    size = 0
    cctx = zstd.ZstdCompressor(level=6, threads=-1, write_checksum=True)
    nonce = os.urandom(12) if enc_key else None
    aes = AESGCM(enc_key) if enc_key else None
    pending = bytearray()  # compressed bytes waiting for encryption
    rs_pending = bytearray()  # bytes waiting for RS encoding
    stats = {"comp_len": 0, "enc_len": 0, "stored_len": 0}
    chunk_idx = 0

    def emit_stage2(data: bytes, final: bool = False):
        nonlocal rs_pending
        stats["enc_len"] += len(data)
        if not use_rs:
            out.write(data)
            stats["stored_len"] += len(data)
            return
        rs_pending += data
        cut = len(rs_pending) if final else (len(rs_pending) // rs.K) * rs.K
        if cut:
            enc = rs.encode(bytes(rs_pending[:cut]))
            out.write(enc)
            stats["stored_len"] += len(enc)
            del rs_pending[:cut]

    def emit_stage1(data: bytes, final: bool = False):
        nonlocal chunk_idx
        stats["comp_len"] += len(data)
        if aes is None:
            emit_stage2(data, final)
            return
        pending.extend(data)
        while len(pending) >= ENC_CHUNK or (final and pending is not None):
            take = bytes(pending[:ENC_CHUNK])
            del pending[:ENC_CHUNK]
            last = final and not pending
            aad = struct.pack(">IIB", file_index, chunk_idx, 1 if last else 0)
            ct = aes.encrypt(_chunk_nonce(nonce, chunk_idx), take, aad)
            chunk_idx += 1
            emit_stage2(ct, final=last)
            if last:
                break

    comp = cctx.compressobj()
    while True:
        buf = src.read(IO_CHUNK)
        if not buf:
            break
        sha.update(buf)
        size += len(buf)
        c = comp.compress(buf)
        if c:
            emit_stage1(c)
    emit_stage1(comp.flush(), final=True)
    return {
        "size": size,
        "sha256": sha.hexdigest(),
        "codec": "zstd",
        "comp_len": stats["comp_len"],
        "enc_len": stats["enc_len"],
        "stored_len": stats["stored_len"],
        "nonce": nonce.hex() if nonce else None,
    }


# --------------------------------------------------------------------------- decode
def unpack_file(stream: BinaryIO, entry: dict, file_index: int, enc_key: bytes | None,
                use_rs: bool, out: BinaryIO) -> dict:
    """Restore one file from the payload stream. Returns verification info."""
    stream.seek(entry["offset"])
    stored = stream.read(entry["stored_len"])
    if len(stored) != entry["stored_len"]:
        raise PayloadError("payload truncated")
    corrected = 0
    if use_rs:
        data, corrected = rs.decode(stored, entry["enc_len"])
    else:
        data = stored
    del stored
    if enc_key:
        from cryptography.exceptions import InvalidTag

        aes = AESGCM(enc_key)
        nonce = bytes.fromhex(entry["nonce"])
        plain = bytearray()
        pos, idx, step = 0, 0, ENC_CHUNK + GCM_TAG
        while pos < len(data):
            ct = data[pos : pos + step]
            pos += step
            last = pos >= len(data)
            aad = struct.pack(">IIB", file_index, idx, 1 if last else 0)
            try:
                plain += aes.decrypt(_chunk_nonce(nonce, idx), ct, aad)
            except InvalidTag as e:
                raise PayloadError("authentication failed (wrong password or corrupted data)") from e
            idx += 1
        data = bytes(plain)
        del plain
    dctx = zstd.ZstdDecompressor()
    sha = hashlib.sha256()
    size = 0
    try:
        reader = dctx.stream_reader(data)
        while True:
            buf = reader.read(IO_CHUNK)
            if not buf:
                break
            sha.update(buf)
            size += len(buf)
            out.write(buf)
    except zstd.ZstdError as e:
        raise PayloadError(f"decompression failed: {e}") from e
    digest = sha.hexdigest()
    return {
        "sha256_actual": digest,
        "size_actual": size,
        "valid": digest == entry["sha256"] and size == entry["size"],
        "rs_corrected_blocks": corrected,
    }
