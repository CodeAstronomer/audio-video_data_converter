"""ffprobe / ffmpeg helpers (raw video frames and raw PCM audio)."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from fractions import Fraction


class MediaError(Exception):
    pass


@dataclass
class MediaInfo:
    has_video: bool = False
    width: int = 0
    height: int = 0
    fps_num: int = 0
    fps_den: int = 1
    n_frames: int = 0
    has_audio: bool = False
    sample_rate: int = 0
    channels: int = 0
    n_samples: int = 0  # estimate (sample frames) until decoded
    duration: float = 0.0
    format_name: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def fps(self) -> Fraction:
        return Fraction(self.fps_num, self.fps_den) if self.fps_num else Fraction(0)

    def to_dict(self) -> dict:
        return {
            "has_video": self.has_video, "width": self.width, "height": self.height,
            "fps": float(self.fps) if self.has_video else 0, "fps_str": f"{self.fps_num}/{self.fps_den}",
            "n_frames": self.n_frames, "has_audio": self.has_audio,
            "sample_rate": self.sample_rate, "channels": self.channels,
            "n_samples": self.n_samples, "duration": self.duration, "format": self.format_name,
        }


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, **kw)


def _frac(s: str | None) -> Fraction | None:
    try:
        f = Fraction(s)
        return f if f > 0 else None
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def probe(path: str, count_frames: bool = True) -> MediaInfo:
    cmd = ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format"]
    p = _run(cmd + [path])
    if p.returncode != 0:
        raise MediaError("ffprobe failed: " + p.stderr.decode(errors="replace")[-500:])
    data = json.loads(p.stdout or b"{}")
    info = MediaInfo()
    fmt = data.get("format", {})
    info.format_name = fmt.get("format_name", "")
    try:
        info.duration = float(fmt.get("duration") or 0)
    except ValueError:
        info.duration = 0.0
    v = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"
              and not s.get("disposition", {}).get("attached_pic")), None)
    a = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    if v:
        info.has_video = True
        info.width, info.height = int(v["width"]), int(v["height"])
        fps = _frac(v.get("avg_frame_rate")) or _frac(v.get("r_frame_rate"))
        if not fps:
            raise MediaError("cannot determine video frame rate")
        fps = fps.limit_denominator(1001000)
        info.fps_num, info.fps_den = fps.numerator, fps.denominator
        n = 0
        if count_frames:
            q = _run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets",
                      "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", path])
            try:
                n = int(q.stdout.decode().strip().split(",")[0])
            except ValueError:
                n = 0
        if not n:
            try:
                n = int(v.get("nb_frames") or 0)
            except ValueError:
                n = 0
        if not n:
            dur = float(v.get("duration") or info.duration or 0)
            n = int(round(dur * float(fps)))
        info.n_frames = n
    if a:
        info.has_audio = True
        info.sample_rate = int(a.get("sample_rate") or 0)
        info.channels = int(a.get("channels") or 0)
        dur = float(a.get("duration") or info.duration or 0)
        info.n_samples = int(dur * info.sample_rate)
        if not info.sample_rate or not info.channels:
            info.has_audio = False
    if not info.has_video and not info.has_audio:
        raise MediaError("no video or audio stream found")
    return info


# --------------------------------------------------------------------------- audio
def decode_audio_raw(src: str, dst_raw: str) -> None:
    """Decode the first audio stream to interleaved s16le PCM (no resampling)."""
    p = _run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", src, "-map", "0:a:0",
              "-vn", "-f", "s16le", "-acodec", "pcm_s16le", dst_raw])
    if p.returncode != 0:
        raise MediaError("audio decode failed: " + p.stderr.decode(errors="replace")[-500:])


def encode_audio_raw(src_raw: str, rate: int, channels: int, dst: str, codec: str) -> None:
    acodec = {"flac": ["-c:a", "flac", "-compression_level", "5"],
              "wav": ["-c:a", "pcm_s16le"]}[codec]
    p = _run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "s16le", "-ar", str(rate),
              "-ac", str(channels), "-i", src_raw, *acodec, dst])
    if p.returncode != 0:
        raise MediaError("audio encode failed: " + p.stderr.decode(errors="replace")[-500:])


# --------------------------------------------------------------------------- video
class FrameReader:
    """Iterate raw rgb24 frames of the first video stream."""

    def __init__(self, src: str, width: int, height: int, stderr_path: str):
        self.size = width * height * 3
        self._err = open(stderr_path, "wb")
        self.proc = subprocess.Popen(
            ["ffmpeg", "-nostdin", "-v", "error", "-i", src, "-map", "0:v:0", "-an", "-sn",
             "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
            stdout=subprocess.PIPE, stderr=self._err, bufsize=self.size)

    def read(self) -> bytes | None:
        buf = self.proc.stdout.read(self.size)
        if not buf or len(buf) < self.size:
            return None
        return buf

    def close(self):
        try:
            self.proc.stdout.close()
        finally:
            self.proc.kill() if self.proc.poll() is None else None
            self.proc.wait()
            self._err.close()


VIDEO_CODECS = {
    "ffv1": ["-c:v", "ffv1", "-level", "3", "-g", "1", "-slices", "4", "-slicecrc", "1",
             "-pix_fmt", "gbrp"],
    "h264": ["-c:v", "libx264rgb", "-qp", "0", "-preset", "veryfast", "-pix_fmt", "rgb24"],
}


class FrameWriter:
    """Encode raw rgb24 frames into a lossless MKV, optionally muxing an audio file."""

    def __init__(self, dst: str, width: int, height: int, fps: Fraction, codec: str,
                 audio_path: str | None, stderr_path: str):
        self._err = open(stderr_path, "wb")
        cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{width}x{height}", "-framerate", f"{fps.numerator}/{fps.denominator}",
               "-i", "-"]
        if audio_path:
            cmd += ["-i", audio_path, "-map", "0:v", "-map", "1:a", "-c:a", "copy"]
        cmd += VIDEO_CODECS[codec] + ["-f", "matroska", dst]
        self.stderr_path = stderr_path
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=self._err)

    def write(self, buf) -> None:
        try:
            self.proc.stdin.write(buf)
        except BrokenPipeError as e:
            raise MediaError("video encoder terminated: " + self._tail()) from e

    def _tail(self) -> str:
        self._err.flush()
        with open(self.stderr_path, "rb") as f:
            return f.read()[-500:].decode(errors="replace")

    def finish(self) -> None:
        try:
            self.proc.stdin.close()
        except BrokenPipeError:
            pass
        rc = self.proc.wait()
        self._err.close()
        if rc != 0:
            raise MediaError("video encode failed: " + self._tail())

    def abort(self):
        if self.proc.poll() is None:
            self.proc.kill()
        self.proc.wait()
        if not self._err.closed:
            self._err.close()
