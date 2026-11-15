import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _ff(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


@pytest.fixture(scope="session")
def media_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("media")
    # lossy H.264 video with AAC audio (typical input)
    _ff("-f", "lavfi", "-i", "testsrc2=size=160x120:rate=25", "-f", "lavfi",
        "-i", "sine=frequency=440:sample_rate=22050", "-t", "4", "-c:v", "libx264",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(d / "video_audio.mp4"))
    # video without audio
    _ff("-f", "lavfi", "-i", "testsrc2=size=176x144:rate=30000/1001", "-t", "3",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(d / "video.mp4"))
    # stereo audio
    _ff("-f", "lavfi", "-i", "sine=frequency=330:sample_rate=44100", "-ac", "2", "-t", "3",
        str(d / "audio.wav"))
    _ff("-f", "lavfi", "-i", "sine=frequency=330:sample_rate=8000", "-t", "2",
        "-c:a", "flac", str(d / "short.flac"))
    return d


@pytest.fixture()
def payload_files(tmp_path):
    files = []
    p = tmp_path / "random.bin"
    p.write_bytes(os.urandom(40_000))
    files.append(("random.bin", str(p)))
    p = tmp_path / "text äöü.txt"
    p.write_text("\n".join(f"Zeile {i}: Sterne, Galaxien und Quasare" for i in range(2000)))
    files.append(("text äöü.txt", str(p)))
    p = tmp_path / "empty.dat"
    p.write_bytes(b"")
    files.append(("empty.dat", str(p)))
    return files
