from termin.default_assets.resource_manager import DefaultResourceManager
from termin.default_assets.handle_accessors import HandleAccessors
from tgfx import TcTexture


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
    assert isinstance(manager.get_handle_accessors("tc_texture"), HandleAccessors)
    assert isinstance(manager.get_handle_accessors("texture_handle"), HandleAccessors)


def test_default_resource_manager_exposes_builtin_asset_registration() -> None:
    manager = DefaultResourceManager()

    manager.register_builtin_textures()
    manager.register_builtin_materials()
    registered_meshes = manager.register_builtin_meshes()

    assert manager.get_texture_asset("__white_1x1__") is not None
    assert manager.get_texture_asset("__normal_1x1__") is not None
    white_texture = manager.get_texture_handle("__white_1x1__")
    normal_texture = manager.get_texture_handle("__normal_1x1__")
    assert isinstance(white_texture, TcTexture)
    assert isinstance(normal_texture, TcTexture)
    assert white_texture.is_valid
    assert normal_texture.is_valid
    assert white_texture.uuid == "__white_1x1__"
    assert normal_texture.uuid == "__normal_1x1__"
    assert manager.get_handle_by_uuid("tc_texture", "__white_1x1__").uuid == "__white_1x1__"
    assert set(registered_meshes) == {"Cube", "Sphere", "Plane", "Cylinder"}
    assert manager.get_mesh_asset("Cube") is not None
