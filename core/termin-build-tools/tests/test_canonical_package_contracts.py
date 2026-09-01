from __future__ import annotations

from pathlib import Path

from termin_build.package_manifest import load_manifest


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_canonical_distribution_and_native_extension_identities() -> None:
    entries = {entry.path: entry for entry in load_manifest(REPO_ROOT)}

    base = entries["core/termin-base"]
    assert base.distribution == "termin-base"
    assert [item.extension for item in base.native_extensions] == [
        "termin.base._base_native",
        "termin.base._geom_native",
    ]
    assert [item.target for item in base.native_extensions] == [
        "_base_native",
        "_geom_native",
    ]

    graphics = entries["graphics/termin-graphics"]
    assert graphics.distribution == "termin-graphics-core"
    assert [item.extension for item in graphics.native_extensions] == [
        "termin.graphics._graphics_native",
    ]
    assert graphics.native_extensions[0].target == "_graphics_native"

    nodegraph = entries["graphics/termin-nodegraph"]
    assert nodegraph.distribution == "termin-nodegraph"
    assert [item.extension for item in nodegraph.native_extensions] == [
        "termin.nodegraph._nodegraph_native",
    ]


def test_graphics_mcp_is_child_namespace_only() -> None:
    entries = {entry.path: entry for entry in load_manifest(REPO_ROOT)}
    assert entries["graphics/termin-graphics"].distribution == "termin-graphics-core"
    assert entries["graphics/termin-graphics-mcp"].distribution == "termin-graphics-mcp"

    graphics_root = (
        REPO_ROOT / "graphics" / "termin-graphics" / "python" / "termin" / "graphics"
    )
    mcp_root = (
        REPO_ROOT
        / "graphics"
        / "termin-graphics-mcp"
        / "termin"
        / "graphics"
    )
    assert (graphics_root / "__init__.py").is_file()
    assert not (mcp_root / "__init__.py").exists()
    assert (mcp_root / "mcp" / "__init__.py").is_file()
