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
    assert TcTexture.from_uuid("5fb7972ad02ddfad").is_valid
    assert TcTexture.from_uuid("07151644d3bb92c7").is_valid
    assert manager.get_texture_asset_by_uuid("5fb7972ad02ddfad") is manager.get_texture_asset(
        "__white_1x1__"
    )
    assert manager.get_texture_asset_by_uuid("07151644d3bb92c7") is manager.get_texture_asset(
        "__normal_1x1__"
    )
    assert set(registered_meshes) == {"Cube", "Sphere", "Plane", "Cylinder"}
    assert manager.get_mesh_asset("Cube") is not None


def test_builtin_pipeline_registration_is_idempotent_without_copying_pipeline() -> None:
    from termin.render_framework import tc_pipeline_registry_count

    manager = DefaultResourceManager()
    baseline = tc_pipeline_registry_count()

    try:
        manager.register_builtin_pipelines()
        after_first = tc_pipeline_registry_count()
        manager.register_builtin_pipelines()

        assert manager.get_pipeline_asset("Triangle") is not None
        assert after_first == baseline + 1
        assert tc_pipeline_registry_count() == after_first
    finally:
        manager.clear_runtime_state()
        assert tc_pipeline_registry_count() == baseline
