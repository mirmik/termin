from termin.default_assets.resource_manager import DefaultResourceManager
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


def test_default_resource_manager_exposes_handle_accessor_contracts() -> None:
    manager = DefaultResourceManager()

    assert isinstance(manager.get_handle_accessors("mesh_handle"), HandleAccessors)
    assert isinstance(manager.get_handle_accessors("texture_handle"), HandleAccessors)
