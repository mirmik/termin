"""Cross-platform file icons drawn with PIL.

All icons are rendered as RGBA numpy arrays and uploaded to GPU on first use.
"""
from __future__ import annotations

import mimetypes
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image, ImageDraw

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# MIME type → icon type
# ---------------------------------------------------------------------------

_EXACT_MIME: dict[str, str] = {
    "application/pdf":         "pdf",
    "application/zip":         "archive",
    "application/gzip":        "archive",
    "application/x-tar":       "archive",
    "application/x-7z-compressed":  "archive",
    "application/x-rar-compressed": "archive",
    "application/x-bzip2":     "archive",
    "application/x-xz":        "archive",
    "application/vnd.debian.binary-package": "archive",
    "application/vnd.ms-excel":                                     "spreadsheet",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "spreadsheet",
    "application/vnd.oasis.opendocument.spreadsheet":               "spreadsheet",
    "application/javascript":  "code",
    "application/json":        "code",
    "application/xml":         "code",
    "application/x-httpd-php": "code",
    "text/html":               "code",
    "text/css":                "code",
    "text/xml":                "code",
}

_CODE_TEXT_SUBTYPES = frozenset({
    "x-python", "x-csrc", "x-c++src", "x-java-source", "x-ruby",
    "x-sh", "x-shellscript", "x-makefile", "x-cmake", "rust",
    "x-go", "x-typescript", "x-kotlin", "x-lua",
})

_EXEC_SUBTYPES = frozenset({
    "x-executable", "x-sharedlib", "x-elf", "x-msdos-program",
    "x-msdownload",
})


def mime_to_icon_type(mime_type: str | None) -> str:
    """Map a MIME type string to one of the known icon type names."""
    if not mime_type:
        return "file"

    exact = _EXACT_MIME.get(mime_type)
    if exact:
        return exact

    main, _, sub = mime_type.partition("/")
    if main == "image":
        return "image"
    if main == "audio":
        return "audio"
    if main == "video":
        return "video"
    if main == "text":
        return "code" if sub in _CODE_TEXT_SUBTYPES else "file"
    if main == "application" and sub in _EXEC_SUBTYPES:
        return "exec"

    return "file"


# ---------------------------------------------------------------------------
# Icon drawing
# ---------------------------------------------------------------------------

def _shade(color: tuple, factor: float) -> tuple:
    r, g, b, a = color
    return (
        max(0, min(255, int(r * factor))),
        max(0, min(255, int(g * factor))),
        max(0, min(255, int(b * factor))),
        a,
    )


_FOLDER_COLOR: tuple = (205, 170, 60, 255)

_FILE_COLORS: dict[str, tuple] = {
    "file":        (140, 155, 175, 255),
    "image":       (80,  185, 120, 255),
    "audio":       (175, 100, 205, 255),
    "video":       (220, 100, 80,  255),
    "archive":     (190, 135, 60,  255),
    "exec":        (80,  200, 145, 255),
    "code":        (100, 155, 225, 255),
    "pdf":         (220, 75,  75,  255),
    "spreadsheet": (80,  190, 100, 255),
}


def _draw_folder(size: int) -> np.ndarray:
    s = size
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = _FOLDER_COLOR
    light = _shade(c, 1.18)

    tab_w = s * 9 // 20
    tab_h = s * 5 // 20

    # Tab (slight trapezoid with angled right edge)
    d.polygon([
        (0, tab_h),
        (0, 2),
        (2, 0),
        (tab_w - 2, 0),
        (tab_w, tab_h),
    ], fill=c)

    # Body
    d.rectangle([0, tab_h, s - 1, s - 2], fill=c)

    # Top highlight on body
    d.line([(0, tab_h), (s - 1, tab_h)], fill=light, width=1)

    return np.array(img, dtype=np.uint8)


def _draw_file(size: int, icon_type: str) -> np.ndarray:
    s = size
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = _FILE_COLORS.get(icon_type, _FILE_COLORS["file"])
    fold = max(3, s * 5 // 20)

    # Main body
    d.polygon([
        (0, 0),
        (s - 1 - fold, 0),
        (s - 1, fold),
        (s - 1, s - 1),
        (0, s - 1),
    ], fill=c)

    # Fold triangle (darker)
    d.polygon([
        (s - 1 - fold, 0),
        (s - 1, fold),
        (s - 1 - fold, fold),
    ], fill=_shade(c, 0.55))

    return np.array(img, dtype=np.uint8)


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------

class FileIconProvider:
    """Lazy provider of GPU texture handles for file and directory icons.

    Call :meth:`get_texture` during widget rendering (OpenGL context active).
    Textures are uploaded once and cached.

    Usage::

        provider = FileIconProvider(size=20)

        # In file list setup:
        icon_type = provider.icon_type_for_file("report.pdf")   # → "pdf"
        icon_type = provider.icon_type_for_directory()          # → "folder"

        # In widget render():
        tex = provider.get_texture(renderer, icon_type)
        renderer.draw_image(x, y, size, size, tex)
    """

    def __init__(self, size: int = 20):
        self._size = size
        self._arrays: dict[str, np.ndarray] = {}
        self._textures: dict[str, object] = {}  # icon_type → GPU texture handle

    @property
    def size(self) -> int:
        return self._size

    @staticmethod
    def icon_type_for_directory() -> str:
        return "folder"

    @staticmethod
    def icon_type_for_file(filename: str) -> str:
        mime, _ = mimetypes.guess_type(filename)
        return mime_to_icon_type(mime)

    def get_texture(self, renderer, icon_type: str):
        """Return GPU texture handle, uploading to GPU on first use."""
        if icon_type not in self._textures:
            arr = self._get_array(icon_type)
            if arr is None:
                return None
            self._textures[icon_type] = renderer.upload_texture(arr)
        return self._textures[icon_type]

    def _get_array(self, icon_type: str) -> np.ndarray | None:
        if icon_type not in self._arrays:
            s = self._size
            if icon_type == "folder":
                self._arrays[icon_type] = _draw_folder(s)
            else:
                self._arrays[icon_type] = _draw_file(s, icon_type)
        return self._arrays[icon_type]
