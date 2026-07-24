from pathlib import Path

from termin_assets import AssetTypeRegistry, PreLoadResult, set_resource_manager_factory
from termin.default_assets.resource_manager import DefaultResourceManager
from termin.default_assets.navmesh.asset import NavMeshAsset
from termin.default_assets.navmesh.asset_plugin import (
    create_import_plugin,
    create_runtime_plugin,
    register_navmesh_import_plugin,
    register_navmesh_runtime_plugin,
)
from termin.default_assets.navmesh.handle import NavMeshHandle
from termin.navmesh._navmesh_native import TcNavMesh
from termin.navmesh.persistence import NavMeshPersistence
from termin.navmesh.types import NavMesh


def test_navmesh_asset_wraps_navmesh() -> None:
    navmesh = NavMesh(name="source_navmesh")

    asset = NavMeshAsset.from_navmesh(navmesh, source_path="/tmp/source.navmesh")

    assert asset.name == "source_navmesh"
    assert asset.navmesh is navmesh
    assert asset.source_path == Path("/tmp/source.navmesh")


def test_navmesh_handle_aliases_canonical_tc_navmesh() -> None:
    navmesh = NavMesh(name="factory_navmesh")
    asset = NavMeshAsset.from_navmesh(
        navmesh,
        name="factory_navmesh",
        source_path="/tmp/factory.navmesh",
    )

    by_name = NavMeshHandle.from_name("factory_navmesh")
    by_uuid = NavMeshHandle.from_uuid(asset.uuid)

    assert NavMeshHandle is TcNavMesh
    assert by_name.is_valid
    assert by_uuid.is_valid
    assert by_name.uuid == asset.uuid
    assert by_uuid.uuid == asset.uuid
    assert TcNavMesh.from_name("factory_navmesh").uuid == asset.uuid


def test_navmesh_asset_declares_core_runtime_resource() -> None:
    navmesh = NavMesh(name="declared_navmesh")
    asset = NavMeshAsset.from_navmesh(
        navmesh,
        name="declared_navmesh",
        source_path="/tmp/declared.navmesh",
    )

    by_uuid = TcNavMesh.from_uuid(asset.uuid)
    by_name = TcNavMesh.from_name("declared_navmesh")

    assert by_uuid.is_valid
    assert by_name.is_valid
    assert by_uuid.uuid == asset.uuid
    assert by_name.uuid == asset.uuid


def test_navmesh_native_resource_lazy_loads_by_canonical_uuid(tmp_path: Path) -> None:
    navmesh_path = tmp_path / "lazy.navmesh"
    NavMeshPersistence.save(NavMesh(name="lazy"), navmesh_path)
    manager = DefaultResourceManager()
    set_resource_manager_factory(lambda: manager)
    try:
        manager.register_file(
            PreLoadResult(
                resource_type="navmesh",
                path=str(navmesh_path),
                content=None,
                uuid="lazy-navmesh-uuid",
                spec_data={"uuid": "lazy-navmesh-uuid"},
            )
        )

        asset = manager.get_navmesh_asset_by_uuid("lazy-navmesh-uuid")
        resource = TcNavMesh.from_uuid("lazy-navmesh-uuid")
        assert asset is not None
        assert resource.is_valid
        assert not asset.is_loaded

        assert resource.ensure_loaded()
        assert asset.is_loaded
    finally:
        set_resource_manager_factory(None)
        manager.clear_runtime_state()


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
