from termin.default_assets.resource_manager import DefaultResourceManager
from termin.player.runtime_package_loader import _load_mesh


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
