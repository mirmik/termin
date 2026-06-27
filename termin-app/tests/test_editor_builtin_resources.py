from termin.assets.resources import ResourceManager
from termin.editor_core.resource_loader import register_editor_builtin_resources
from tgfx import TcTexture


def test_editor_builtin_resources_include_render_assets() -> None:
    resource_manager = ResourceManager()

    try:
        register_editor_builtin_resources(resource_manager)

        assert resource_manager.get_component("MeshRenderer") is not None
        assert resource_manager.get_frame_pass("UIWidgetPass") is not None
        assert resource_manager.get_mesh_asset("Cube") is not None
        assert resource_manager.get_texture_asset("__white_1x1__") is not None
        assert resource_manager.get_texture_asset("__normal_1x1__") is not None
        assert TcTexture.from_uuid("5fb7972ad02ddfad").is_valid
        assert TcTexture.from_uuid("07151644d3bb92c7").is_valid
        assert resource_manager.get_pipeline_asset("Triangle") is not None
    finally:
        resource_manager.clear_runtime_state()
