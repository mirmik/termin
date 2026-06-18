from termin.default_assets.resource_manager import DefaultResourceManager
from termin.default_assets.resource_manager import DefaultResourceManagerBase


def test_default_resource_manager_owns_default_runtime_registries() -> None:
    manager = DefaultResourceManager()

    assert "prefab" in manager._runtime_asset_registries
    assert "glb" in manager._runtime_asset_registries
    assert "animation_clip" in manager._runtime_asset_registries
    assert "skeleton" in manager._runtime_asset_registries
    assert "pipeline" in manager._runtime_asset_registries
    assert manager.get_material("__missing__") is None


def test_app_resource_manager_base_reexports_default_base() -> None:
    from termin.assets.resources._base import ResourceManagerBase

    assert ResourceManagerBase is DefaultResourceManagerBase
