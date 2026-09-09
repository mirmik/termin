"""Reproducible app-icon exports from the approved, unmodified generated T."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]
MASTER = ROOT / "assets/branding/icons/05-folded-t.png"
DESTINATION = ROOT / "editor/termin-app/termin/resources/icons"
SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)
LOG = logging.getLogger("termin.icon")


def build(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="termin-icon-") as temp:
        work = Path(temp)
        for size in SIZES:
            # Discard the generated alpha, preserving the RGB appearance that
            # was approved on the opaque comparison sheet. No background mask.
            subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-y",
                    "-i",
                    str(MASTER),
                    "-vf",
                    f"format=rgb24,scale={size}:{size}:flags=lanczos",
                    "-frames:v",
                    "1",
                    str(work / f"{size}.png"),
                ],
                check=True,
            )
        bmp = work / "icon.bmp"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-i",
                str(work / "256.png"),
                "-pix_fmt",
                "bgr24",
                "-frames:v",
                "1",
                str(bmp),
            ],
            check=True,
        )
        frames = [(work / f"{s}.png").read_bytes() for s in SIZES]
        entries = []
        offset = 6 + 16 * len(frames)
        for size, data in zip(SIZES, frames):
            assert data[:8] == b"\x89PNG\r\n\x1a\n"
            assert struct.unpack_from(">II", data, 16) == (size, size)
            assert data[24:26] == bytes((8, 2)), "Expected 8-bit opaque RGB PNG"
            entries.append(struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 24, len(data), offset))
            offset += len(data)
        ico = work / "icon.ico"
        ico.write_bytes(struct.pack("<HHH", 0, 1, len(frames)) + b"".join(entries) + b"".join(frames))
        bitmap = bmp.read_bytes()
        assert bitmap[:2] == b"BM"
        assert struct.unpack_from("<ii", bitmap, 18) == (256, 256)
        assert struct.unpack_from("<H", bitmap, 28)[0] == 24
        for source, suffix in [(work / "256.png", "png"), (bmp, "bmp"), (ico, "ico")]:
            shutil.copyfile(source, destination / f"termin-editor-icon.{suffix}")
    LOG.info("Exported opaque T icon to %s; ICO sizes: %s", destination, SIZES)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DESTINATION)
    try:
        build(parser.parse_args().output.resolve())
    except Exception:
        LOG.exception("Icon export failed")
        raise
