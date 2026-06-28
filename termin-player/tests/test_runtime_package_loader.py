from termin.default_assets.resource_manager import DefaultResourceManager
from termin.player.runtime_package_loader import (
    _load_mesh,
    _material_texture_resources_from_shader_spec,
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
