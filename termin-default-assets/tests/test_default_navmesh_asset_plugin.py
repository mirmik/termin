from pathlib import Path

from termin_assets import AssetTypeRegistry, set_resource_manager_factory
from termin.default_assets.navmesh.asset import NavMeshAsset
from termin.default_assets.navmesh.asset_plugin import (
    create_import_plugin,
    create_runtime_plugin,
    register_navmesh_import_plugin,
    register_navmesh_runtime_plugin,
)
from termin.default_assets.navmesh.handle import NavMeshHandle
from termin.navmesh._navmesh_native import TcNavMesh
from termin.navmesh.types import NavMesh


def test_navmesh_asset_wraps_navmesh() -> None:
    navmesh = NavMesh(name="source_navmesh")

    asset = NavMeshAsset.from_navmesh(navmesh, source_path="/tmp/source.navmesh")

    assert asset.name == "source_navmesh"
    assert asset.navmesh is navmesh
    assert asset.source_path == Path("/tmp/source.navmesh")


def test_navmesh_handle_uses_configured_resource_manager_factory() -> None:
    navmesh = NavMesh(name="factory_navmesh")
    asset = NavMeshAsset.from_navmesh(
        navmesh,
        name="factory_navmesh",
        source_path="/tmp/factory.navmesh",
    )

    class FakeResourceManager:
        def get_navmesh_asset(self, name: str):
            return asset if name == asset.name else None

        def get_navmesh_asset_by_uuid(self, uuid: str):
            return asset if uuid == asset.uuid else None

    set_resource_manager_factory(FakeResourceManager)
    try:
        by_name = NavMeshHandle.from_name("factory_navmesh")
        by_uuid = NavMeshHandle.from_uuid(asset.uuid)
    finally:
        set_resource_manager_factory(None)

    assert by_name.asset is asset
    assert by_name.navmesh is navmesh
    assert by_uuid.asset is asset
    assert by_uuid.navmesh is navmesh
    assert by_name.native.is_valid
    assert by_name.native.uuid == asset.uuid
    assert TcNavMesh.from_name("factory_navmesh").uuid == asset.uuid


def test_navmesh_asset_declares_core_runtime_resource() -> None:
    navmesh = NavMesh(name="declared_navmesh")
    asset = NavMeshAsset.from_navmesh(
        navmesh,
        name="declared_navmesh",
        source_path="/tmp/declared.navmesh",
    )

    handle = NavMeshHandle.from_asset(asset)
    by_uuid = TcNavMesh.from_uuid(asset.uuid)
    by_name = TcNavMesh.from_name("declared_navmesh")

    assert handle.native.is_valid
    assert by_uuid.is_valid
    assert by_name.is_valid
    assert by_uuid.uuid == asset.uuid
    assert by_name.uuid == asset.uuid


def test_navmesh_plugins_register_with_asset_registry() -> None:
    registry = AssetTypeRegistry()

    register_navmesh_import_plugin(registry)
    register_navmesh_runtime_plugin(registry)

    assert registry.get_import("navmesh") is not None
    assert registry.get_runtime("navmesh") is not None
    assert registry.get_for_extension(".navmesh")[0].type_id == "navmesh"


def test_navmesh_entry_point_factories() -> None:
    assert create_import_plugin().type_id == "navmesh"
    assert create_runtime_plugin().type_id == "navmesh"
