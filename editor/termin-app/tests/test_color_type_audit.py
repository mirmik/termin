from __future__ import annotations

from pathlib import Path
import re


_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_SKIP_PARTS = {
    ".agents",
    ".codex",
    ".git",
    "build",
    "docs",
    "Generated",
    "sdk",
    "thirdparty",
    "termin-thirdparty",
}
_TEXT_SUFFIXES = {".c", ".cc", ".cpp", ".cs", ".h", ".hpp", ".py", ".pyi"}
_OWNED_ROOTS = (
    "editor/termin-app",
    "core/termin-base",
    "engine/termin-components",
    "termin-csharp",
    "engine/termin-engine",
    "graphics/termin-graphics",
    "graphics/termin-gui-native",
    "graphics/termin-materials",
    "graphics/termin-mesh",
    "physics/termin-navmesh",
    "engine/termin-render",
    "engine/termin-render-passes",
    "graphics/termin-visual-scene",
    "platform/termin-web-core",
    "graphics/tcplot",
)
_LEGACY_COLOR4 = re.compile(r"\b" + "Color" + r"4f?\b|\bVisual" + "Color" + r"4f\b")
_LEGACY_UI_COLOR = re.compile(r"\btc_ui_color\b")
_LEGACY_SHADER_COLOR_PROPERTY = re.compile(r"@property\s+Color(?:\s|$)")
_MATERIAL_LEGACY_SET_COLOR = re.compile(r"\b(?:phase|material|mat)\.set_color\s*\(")
_LEGACY_COLOR_DECLARATION = re.compile(r"\b(?:class|struct|using|typedef)\s+Color\b|^Color\s*=", re.MULTILINE)
_LEGACY_MATERIAL_COLOR_API = re.compile(r"\btc_material(?:_phase)?_(?:get|set)_color\b")


def _source_files(*roots: str):
    """Yield first-party source files below roots, excluding generated/vendor data."""
    for root in roots:
        base = _REPOSITORY_ROOT / root
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix not in _TEXT_SUFFIXES:
                continue
            if _SKIP_PARTS.intersection(path.parts):
                continue
            yield path


def test_first_party_sources_do_not_use_legacy_color4_types():
    findings: list[str] = []
    for path in _source_files(*_OWNED_ROOTS):
        text = path.read_text(encoding="utf-8")
        if _LEGACY_COLOR4.search(text):
            findings.append(str(path.relative_to(_REPOSITORY_ROOT)))

    assert findings == [], "legacy " + "Color" + "4 types remain in owned sources: " + ", ".join(findings)


def test_first_party_sources_do_not_use_legacy_ui_color_type():
    findings = [
        str(path.relative_to(_REPOSITORY_ROOT))
        for path in _source_files(
            "editor/termin-app",
            "engine/termin-components",
            "engine/termin-engine",
            "graphics/termin-graphics",
            "graphics/termin-gui-native",
            "graphics/termin-materials",
            "engine/termin-render",
            "engine/termin-render-passes",
            "graphics/termin-visual-scene",
            "platform/termin-web-core",
        )
        if path != Path(__file__) and _LEGACY_UI_COLOR.search(path.read_text(encoding="utf-8"))
    ]
    assert findings == [], "legacy tc_ui_color boundaries remain: " + ", ".join(findings)


def test_first_party_sources_do_not_declare_ambiguous_color_types():
    findings = []
    for path in _source_files(*_OWNED_ROOTS):
        if path == Path(__file__):
            continue
        if _LEGACY_COLOR_DECLARATION.search(path.read_text(encoding="utf-8")):
            findings.append(str(path.relative_to(_REPOSITORY_ROOT)))
    assert findings == [], "ambiguous Color type declarations remain: " + ", ".join(findings)


def test_legacy_shader_color_is_confined_to_rejection_fixture():
    fixture = _REPOSITORY_ROOT / "graphics/termin-materials/tests/test_shader_parser.py"
    findings = []
    for path in _source_files("graphics/termin-materials", "platform/termin-web-core"):
        if path == fixture:
            continue
        if _LEGACY_SHADER_COLOR_PROPERTY.search(path.read_text(encoding="utf-8")):
            findings.append(str(path.relative_to(_REPOSITORY_ROOT)))
    assert findings == [], "legacy shader Color property escaped its rejection fixture: " + ", ".join(findings)


def test_material_callers_use_typed_color_setters():
    findings = []
    for path in _source_files(
        "graphics/termin-materials/python", "graphics/termin-materials/src"
    ):
        if _MATERIAL_LEGACY_SET_COLOR.search(path.read_text(encoding="utf-8")):
            findings.append(str(path.relative_to(_REPOSITORY_ROOT)))
    assert findings == [], (
        "ambiguous material set_color callers remain; use set_uniform_srgb_color or "
        "set_uniform_linear_color: " + ", ".join(findings)
    )


def test_material_apis_have_no_legacy_color_scaffold():
    handle = (
        _REPOSITORY_ROOT
        / "graphics/termin-graphics/include/tgfx/tgfx_material_handle.hpp"
    )
    text = handle.read_text(encoding="utf-8")
    assert "set_uniform_srgb_color" in text
    assert "set_uniform_linear_color" in text
    assert re.search(r"\bvoid\s+set_color\s*\(", text) is None

    findings = []
    for path in _source_files(
        "engine/termin-components",
        "termin-csharp",
        "graphics/termin-graphics",
        "graphics/termin-materials",
    ):
        if _LEGACY_MATERIAL_COLOR_API.search(path.read_text(encoding="utf-8")):
            findings.append(str(path.relative_to(_REPOSITORY_ROOT)))
    assert findings == [], "ambiguous C material color APIs remain: " + ", ".join(findings)
