from termin.assets.resources import ResourceManager
from termin.editor_core.default_preloaders import create_default_preloaders
from termin.editor_core.plugin_preloader import PluginPreLoader
from termin_assets import PreLoadResult


def test_mesh_register_file_uses_asset_plugin() -> None:
    rm = ResourceManager()
    result = PreLoadResult(
        resource_type="mesh",
        path="/tmp/plugin_probe.obj",
        content=None,
        uuid="mesh-plugin-test-uuid",
        spec_data={"uuid": "mesh-plugin-test-uuid", "scale": 2.0},
    )

    rm.register_file(result)

    asset = rm.get_mesh_asset("plugin_probe")
    assert asset is not None
    assert asset.uuid == "mesh-plugin-test-uuid"
    assert asset.source_path is not None
    assert str(asset.source_path) == "/tmp/plugin_probe.obj"
    assert rm.get_asset_by_uuid("mesh-plugin-test-uuid") is asset


def test_asset_plugin_registry_can_find_mesh_by_extension() -> None:
    rm = ResourceManager()
    plugins = rm.asset_type_plugins.get_for_extension(".obj")

    assert len(plugins) == 1
    assert plugins[0].type_id == "mesh"


def test_default_preloaders_use_plugin_adapter_for_mesh() -> None:
    rm = ResourceManager()
    preloaders = create_default_preloaders(rm)
    mesh_preloaders = [
        preloader
        for preloader in preloaders
        if ".obj" in preloader.extensions
    ]

    assert len(mesh_preloaders) == 1
    assert isinstance(mesh_preloaders[0], PluginPreLoader)
    assert mesh_preloaders[0].resource_type == "mesh"
