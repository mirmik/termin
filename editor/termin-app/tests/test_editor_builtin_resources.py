from termin.editor_core.resource_manager import ResourceManager
from termin.editor_core.resource_loader import register_editor_builtin_resources
from termin.graphics import TcTexture
from termin.bootstrap import bootstrap_editor, shutdown_editor
from termin.render_framework import tc_pass_registry_get_class
from termin.scene import ComponentRegistry


def test_editor_builtin_resources_include_render_assets() -> None:
    bootstrap_editor()
    resource_manager = ResourceManager()

    try:
        register_editor_builtin_resources(resource_manager)

        assert ComponentRegistry.instance().get_class("MeshRenderer") is not None
        assert tc_pass_registry_get_class("UIWidgetPass") is not None
        assert resource_manager.get_mesh_asset("Cube") is not None
        assert resource_manager.get_texture_asset("__white_1x1__") is not None
        assert resource_manager.get_texture_asset("__normal_1x1__") is not None
        assert not TcTexture.from_uuid("5fb7972ad02ddfad").is_valid
        assert not TcTexture.from_uuid("07151644d3bb92c7").is_valid
        assert resource_manager.get_pipeline_asset("Triangle") is not None
    finally:
        resource_manager.clear_runtime_state()
        shutdown_editor()
