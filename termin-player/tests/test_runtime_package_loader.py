import sys

import numpy as np
import pytest

from termin.default_assets.resource_manager import DefaultResourceManager
from termin.image import write_png_rgba8_file
from termin.player import runtime_package_loader
from termin.player.runtime_package_loader import (
    _load_mesh,
    _load_texture,
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


def test_runtime_package_loader_registers_packaged_texture_before_materials(tmp_path, monkeypatch) -> None:
    manager = DefaultResourceManager()
    monkeypatch.setattr(DefaultResourceManager, "instance", classmethod(lambda cls: manager))

    package_dir = tmp_path / "package"
    source_path = package_dir / "textures" / "albedo.png"
    source_path.parent.mkdir(parents=True)
    write_png_rgba8_file(source_path, np.full((1, 1, 4), 255, dtype=np.uint8))

    assert _load_texture(
        package_dir,
        {
            "uuid": "runtime-texture-uuid",
            "name": "RuntimeAlbedo",
            "source_path": "textures/albedo.png",
            "import_settings": {"flip_x": True, "flip_y": False, "transpose": True},
        },
        package_dir / "textures" / "runtime-texture-uuid.texture.json",
    )

    texture_asset = manager.get_texture_asset_by_uuid("runtime-texture-uuid")
    assert texture_asset is not None
    assert texture_asset.source_path == source_path
    assert texture_asset.flip_x is True
    assert texture_asset.flip_y is False
    assert texture_asset.transpose is True
    assert texture_asset.texture_data is not None
    assert texture_asset.texture_data.is_valid


def test_runtime_package_loader_orders_textures_before_materials(tmp_path, monkeypatch) -> None:
    package_dir = tmp_path / "package"
    package_dir.mkdir()
    manifest_path = package_dir / "manifest.json"
    manifest_path.write_text(
        """
{
  "resources": [
    {"type": "material", "path": "materials/example.tmat.json"},
    {"type": "texture", "path": "textures/example.texture.json"},
    {"type": "shader", "path": "shaders/example.shader.json"}
  ]
}
""".strip(),
        encoding="utf-8",
    )
    loaded_types: list[str] = []

    monkeypatch.setattr(runtime_package_loader, "_configure_shader_runtime", lambda *_args: True)

    def load_resource(_package_dir, entry, _shaders) -> bool:
        loaded_types.append(entry["type"])
        return True

    monkeypatch.setattr(runtime_package_loader, "_load_resource", load_resource)

    runtime_package_loader.load_runtime_package_assets(package_dir, manifest_path)

    assert loaded_types == ["shader", "texture", "material"]


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
