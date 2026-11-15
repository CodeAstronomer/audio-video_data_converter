"""Vectorised Reed-Solomon RS(255,223) over GF(2^8).

Encoding (and error *detection*) is done with numpy for many codewords in
parallel.  Only codewords that actually contain errors are handed to the
pure-Python ``reedsolo`` decoder for correction.  The code is byte
compatible with ``reedsolo.RSCodec(32)`` (prim 0x11d, generator 2, fcr 0).
"""
from __future__ import annotations

import numpy as np

NSYM = 32
N = 255
K = N - NSYM  # 223 data bytes per codeword

_PRIM = 0x11D


def _build_tables():
    exp = np.zeros(512, dtype=np.int32)
    log = np.zeros(256, dtype=np.int32)
    x = 1
    for i in range(255):
        exp[i] = x
        log[x] = i
        x <<= 1
        if x & 0x100:
            x ^= _PRIM
    for i in range(255, 512):
        exp[i] = exp[i - 255]
    a = np.arange(256)
    mul = exp[(log[a][:, None] + log[a][None, :]) % 255].astype(np.uint8)
    mul[0, :] = 0
    mul[:, 0] = 0
    return exp, log, mul


_EXP, _LOG, _MUL = _build_tables()


def _generator(nsym: int) -> np.ndarray:
    g = [1]
    for i in range(nsym):
        # multiply g by (x - alpha^i)
        root = int(_EXP[i])
        ng = [0] * (len(g) + 1)
        for j, c in enumerate(g):
            ng[j] ^= c
            ng[j + 1] ^= int(_MUL[c, root])
        g = ng
    return np.array(g, dtype=np.uint8)


_GEN = _generator(NSYM)  # monic, _GEN[0] == 1
# _MULG[c, j] = gen[j+1] * c
_MULG = _MUL[:, _GEN[1:].astype(np.intp)]
# Rolled tables for a circular shift register (avoids shifting every step).
# Row h: table to XOR when the register head is at column h.
_ROLLED = []
for _h in range(NSYM):
    t = np.zeros((256, NSYM), dtype=np.uint8)
    for _j in range(NSYM):
        t[:, (_h + 1 + _j) % NSYM] = _MULG[:, _j]
    _ROLLED.append(np.ascontiguousarray(t).view(np.uint64))  # (256, 4)


def _parity(data: np.ndarray) -> np.ndarray:
    """data: (B, K) uint8 -> parity bytes (B, NSYM)."""
    b = data.shape[0]
    reg = np.zeros((b, NSYM), dtype=np.uint8)
    reg64 = reg.view(np.uint64)
    for i in range(K):
        h = i % NSYM
        coef = data[:, i] ^ reg[:, h]
        reg[:, h] = 0
        reg64 ^= _ROLLED[h][coef]
    # logical order starts at head = K % NSYM
    h = K % NSYM
    return np.roll(reg, -h, axis=1)


BATCH = 1 << 15  # codewords per numpy batch


def encoded_len(n: int) -> int:
    return -(-n // K) * N


def encode(data: bytes) -> bytes:
    """Encode ``data`` (zero padded to a multiple of 223) into 255-byte codewords."""
    if not data:
        return b""
    arr = np.frombuffer(data, dtype=np.uint8)
    blocks = -(-len(arr) // K)
    padded = np.zeros(blocks * K, dtype=np.uint8)
    padded[: len(arr)] = arr
    padded = padded.reshape(blocks, K)
    out = np.empty((blocks, N), dtype=np.uint8)
    for s in range(0, blocks, BATCH):
        chunk = padded[s : s + BATCH]
        out[s : s + BATCH, :K] = chunk
        out[s : s + BATCH, K:] = _parity(chunk)
    return out.tobytes()


class RSDecodeError(Exception):
    pass


def decode(data: bytes, out_len: int) -> tuple[bytes, int]:
    """Decode codewords; returns (payload[:out_len], corrected_codewords)."""
    if out_len == 0:
        return b"", 0
    if len(data) % N:
        raise RSDecodeError("RS data length is not a multiple of 255")
    arr = np.frombuffer(data, dtype=np.uint8).reshape(-1, N).copy()
    bad_idx = []
    for s in range(0, arr.shape[0], BATCH):
        chunk = arr[s : s + BATCH]
        par = _parity(chunk[:, :K])
        bad = np.nonzero(np.any(par != chunk[:, K:], axis=1))[0]
        bad_idx.extend((bad + s).tolist())
    if bad_idx:
        import reedsolo

        codec = reedsolo.RSCodec(NSYM)
        for i in bad_idx:
            try:
                msg = codec.decode(bytearray(arr[i].tobytes()))[0]
            except reedsolo.ReedSolomonError as e:  # pragma: no cover
                raise RSDecodeError(f"codeword {i} not correctable: {e}") from e
            arr[i, :K] = np.frombuffer(bytes(msg), dtype=np.uint8)
    return arr[:, :K].tobytes()[:out_len], len(bad_idx)
