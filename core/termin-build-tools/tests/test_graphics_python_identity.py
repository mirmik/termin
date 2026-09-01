"""Regression tests for the public graphics Python package identities."""

from __future__ import annotations

from pathlib import Path

from termin_build.package_manifest import load_manifest


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_graphics_manifest_uses_canonical_mesh_and_plot_identities() -> None:
    packages = {entry.distribution: entry for entry in load_manifest(REPO_ROOT)}

    expected = {
        "termin-mesh": ("termin.mesh._mesh_native",),
        "termin-plot": ("termin.plot._plot_native",),
        "termin-plot-gui-native": ("termin.plot.gui_native._plot_gui_native",),
    }
    for distribution, extensions in expected.items():
        package = packages[distribution]
        assert tuple(extension.extension for extension in package.native_extensions) == extensions

    assert not {"tmesh", "tcplot", "tcplot-gui-native"} & packages.keys()


def test_mesh_package_init_has_one_distribution_owner() -> None:
    """A namespace package's concrete ``__init__`` must not be split across wheels."""
    owners = []
    for package in load_manifest(REPO_ROOT):
        candidate = REPO_ROOT / package.path / "python" / "termin" / "mesh" / "__init__.py"
        if candidate.is_file():
            owners.append(package.distribution)

    assert owners == ["termin-mesh"]

    components = next(
        entry
        for entry in load_manifest(REPO_ROOT)
        if entry.distribution == "termin-components-mesh"
    )
    components_root = REPO_ROOT / components.path / "python" / "termin" / "mesh"
    assert not (components_root / "__init__.py").exists()
    assert (components_root / "components").is_dir()
    assert tuple(extension.extension for extension in components.native_extensions) == (
        "termin.mesh.components._components_mesh_native",
    )
