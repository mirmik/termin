from termin.default_assets.resource_manager import DefaultResourceManager
from termin.default_assets.resource_manager import DefaultResourceManagerBase
from termin.default_assets.handle_accessors import HandleAccessors


def test_default_resource_manager_owns_default_runtime_registries() -> None:
    manager = DefaultResourceManager()

    assert "prefab" in manager._runtime_asset_registries
    assert "glb" in manager._runtime_asset_registries
    assert "animation_clip" in manager._runtime_asset_registries
    assert "skeleton" in manager._runtime_asset_registries
    assert "pipeline" in manager._runtime_asset_registries
    assert manager.get_material("__missing__") is None
    assert isinstance(manager.get_handle_accessors("tc_material"), HandleAccessors)


def test_app_resource_manager_base_reexports_default_base() -> None:
    from termin.assets.resources._base import ResourceManagerBase

    assert ResourceManagerBase is DefaultResourceManagerBase


def test_app_handle_accessors_reexport_default_accessors() -> None:
    from termin.assets.resources._handle_accessors import HandleAccessors as AppHandleAccessors

    assert AppHandleAccessors is HandleAccessors
