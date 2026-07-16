from pathlib import Path

import numpy as np

from termin_assets import AssetContext, AssetTypeRegistry, PreLoadResult
from termin.default_assets.mesh.asset import MeshAsset
from termin.default_assets.mesh.asset_plugin import (
    create_import_plugin,
    create_runtime_plugin,
    register_mesh_import_plugin,
    register_mesh_runtime_plugin,
)
from termin.default_assets.mesh.mesh_spec import DEFAULT_AXIS_X, DEFAULT_AXIS_Y, DEFAULT_AXIS_Z, MeshSpec
from tmesh import Mesh3


class FakeResourceManager:
    def __init__(self) -> None:
        self.by_name = {}
        self.by_uuid = {}

    def get_runtime_asset(self, type_id: str, name: str):
        return self.by_name.get((type_id, name))

    def get_runtime_asset_by_uuid(self, type_id: str, uuid: str):
        return self.by_uuid.get((type_id, uuid))

    def register_runtime_asset(self, type_id: str, name: str, asset, *, source_path=None, uuid=None) -> None:
        self.by_name[(type_id, name)] = asset
        if uuid is not None:
            self.by_uuid[(type_id, uuid)] = asset


class FakeLoadedMeshAsset:
    is_loaded = True

    def __init__(self) -> None:
        self.parsed_spec = None
        self.reload_count = 0

    def should_reload_from_file(self) -> bool:
        return True

    def parse_spec(self, spec_data) -> None:
        self.parsed_spec = spec_data

    def reload(self) -> None:
        self.reload_count += 1


def test_mesh_asset_wraps_mesh3() -> None:
    mesh3 = Mesh3(
        vertices=np.array(
            [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
            ],
            dtype=np.float32,
        ),
        triangles=np.array([[0, 1, 2]], dtype=np.uint32),
        name="triangle",
    )

    asset = MeshAsset.from_mesh3(mesh3, name="triangle", source_path="/tmp/triangle.obj")

    assert asset.name == "triangle"
    assert asset.mesh_data is not None
    assert asset.mesh_data.is_valid
    assert asset.get_vertex_count() == 3
    assert asset.get_triangle_count() == 1
    assert asset.source_path == Path("/tmp/triangle.obj")


def test_mesh_asset_does_not_expose_gpu_lifecycle_api() -> None:
    asset = MeshAsset(name="triangle")

    assert not hasattr(asset, "draw_gpu")
    assert not hasattr(asset, "delete_gpu")


def test_mesh_spec_defaults_live_in_default_assets() -> None:
    spec = MeshSpec()

    assert spec.axis_x == DEFAULT_AXIS_X
    assert spec.axis_y == DEFAULT_AXIS_Y
    assert spec.axis_z == DEFAULT_AXIS_Z


def test_mesh_plugins_register_with_asset_registry() -> None:
    registry = AssetTypeRegistry()

    register_mesh_import_plugin(registry)
    register_mesh_runtime_plugin(registry)

    assert registry.get_import("mesh") is not None
    assert registry.get_runtime("mesh") is not None
    assert registry.get_for_extension(".OBJ")[0].type_id == "mesh"


def test_mesh_runtime_plugin_registers_lazy_asset() -> None:
    resource_manager = FakeResourceManager()
    result = PreLoadResult(
        resource_type="mesh",
        path="/tmp/triangle.obj",
        uuid="mesh-uuid",
        spec_data={"scale": 2.0},
    )

    create_runtime_plugin().register(
        AssetContext(resource_manager=resource_manager, name="triangle"),
        result,
    )

    asset = resource_manager.get_runtime_asset("mesh", "triangle")
    assert isinstance(asset, MeshAsset)
    assert asset.uuid == "mesh-uuid"
    assert asset.source_path == Path("/tmp/triangle.obj")
    assert asset._scale == 2.0


def test_mesh_runtime_reload_stays_in_asset_layer() -> None:
    resource_manager = FakeResourceManager()
    asset = FakeLoadedMeshAsset()
    same_name_asset = FakeLoadedMeshAsset()
    resource_manager.by_name[("mesh", "triangle")] = same_name_asset
    resource_manager.by_uuid[("mesh", "mesh-uuid")] = asset
    result = PreLoadResult(
        resource_type="mesh",
        path="/tmp/triangle.obj",
        uuid="mesh-uuid",
        spec_data={"scale": 2.0},
    )

    create_runtime_plugin().reload(
        AssetContext(resource_manager=resource_manager, name="triangle"),
        result,
    )

    assert asset.parsed_spec == {"scale": 2.0}
    assert asset.reload_count == 1
    assert same_name_asset.reload_count == 0


def test_mesh_entry_point_factories() -> None:
    assert create_import_plugin().type_id == "mesh"
    assert create_runtime_plugin().type_id == "mesh"
