from __future__ import annotations

from pathlib import Path
import re


_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_SKIP_PARTS = {
    ".agents",
    ".codex",
    ".git",
    "build",
    "docs",
    "sdk",
    "thirdparty",
    "termin-thirdparty",
}
_TEXT_SUFFIXES = {".c", ".cc", ".cpp", ".h", ".hpp", ".py", ".pyi"}
_LEGACY_COLOR4 = re.compile(r"\b" + "Color" + r"4f?\b")


def test_first_party_sources_do_not_use_legacy_color4_types():
    findings: list[str] = []
    for path in _REPOSITORY_ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in _TEXT_SUFFIXES:
            continue
        if _SKIP_PARTS.intersection(path.parts):
            continue
        text = path.read_text(encoding="utf-8")
        if _LEGACY_COLOR4.search(text):
            findings.append(str(path.relative_to(_REPOSITORY_ROOT)))

    assert findings == [], "legacy " + "Color" + "4 types remain in owned sources: " + ", ".join(findings)
