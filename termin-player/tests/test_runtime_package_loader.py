import sys

import pytest

from termin.default_assets.resource_manager import DefaultResourceManager
from termin.player.runtime_package_loader import (
    _load_mesh,
    _material_texture_resources_from_shader_spec,
    _package_path,
)


def test_runtime_shader_layout_collects_material_texture_resources(tmp_path) -> None:
    package_dir = tmp_path / "package"
    layout_path = package_dir / "shaders" / "vulkan" / "pbr.frag.spv.layout.json"
    layout_path.parent.mkdir(parents=True)
    layout_path.write_text(
        """
{
  "resources": [
    {"name": "material", "kind": "constant_buffer", "scope": "material"},
    {"name": "u_albedo_texture", "kind": "texture", "scope": "material"},
    {"name": "u_normal_texture", "kind": "texture", "scope": "material"},
    {"name": "shadow_maps", "kind": "texture", "scope": "pass"}
  ]
}
""".strip(),
        encoding="utf-8",
    )

    assert _material_texture_resources_from_shader_spec(
        package_dir,
        {"artifacts": {"vulkan": {"fragment": "shaders/vulkan/pbr.frag.spv"}}},
    ) == ("u_albedo_texture", "u_normal_texture")


def test_runtime_package_loader_registers_meshes_in_default_resource_manager(tmp_path, monkeypatch) -> None:
    manager = DefaultResourceManager()

    monkeypatch.setattr(
        DefaultResourceManager,
        "instance",
        classmethod(lambda cls: manager),
    )

    mesh_uuid = "runtime-loader-default-manager-mesh-uuid"
    spec = {
        "uuid": mesh_uuid,
        "name": "RuntimeTriangle",
        "layout": [
            {"name": "POSITION", "type": "float32", "components": 3, "location": 0},
        ],
        "vertices": [
            0.0,
            0.0,
            0.0,
            1.0,
            0.0,
            0.0,
            0.0,
            1.0,
            0.0,
        ],
        "indices": [0, 1, 2],
    }

    assert _load_mesh(spec, tmp_path / "RuntimeTriangle.mesh.json")
    assert manager.get_mesh_asset_by_uuid(mesh_uuid) is not None


def test_runtime_package_path_rejects_traversal_and_allows_internal_symlinks(tmp_path) -> None:
    package_root = tmp_path / "package"
    package_root.mkdir()
    (package_root / "shaders").mkdir()
    target = package_root / "shaders" / "source.glsl"
    target.write_text("void main() {}", encoding="utf-8")
    try:
        (package_root / "shaders" / "alias.glsl").symlink_to(target)
    except OSError as error:
        if sys.platform == "win32" and error.winerror == 1314:
            pytest.skip("Windows symlink capability is unavailable (WinError 1314)")
        raise

    assert _package_path(package_root, "shaders/alias.glsl") == target

    for invalid in (".", "../outside", "/outside", r"shaders\\source.glsl"):
        try:
            _package_path(package_root, invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"path was accepted: {invalid}")

    outside = tmp_path / "outside.glsl"
    outside.write_text("outside", encoding="utf-8")
    (package_root / "shaders" / "outside.glsl").symlink_to(outside)
    try:
        _package_path(package_root, "shaders/outside.glsl")
    except ValueError:
        pass
    else:
        raise AssertionError("symlink escape was accepted")
