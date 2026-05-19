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


def test_audio_clip_register_file_uses_asset_plugin() -> None:
    rm = ResourceManager()
    result = PreLoadResult(
        resource_type="audio_clip",
        path="/tmp/plugin_probe.wav",
        content=None,
        uuid="audio-plugin-test-uuid",
        spec_data={"uuid": "audio-plugin-test-uuid"},
    )

    rm.register_file(result)

    asset = rm.get_audio_clip_asset("plugin_probe")
    assert asset is not None
    assert asset.uuid == "audio-plugin-test-uuid"
    assert asset.source_path is not None
    assert str(asset.source_path) == "/tmp/plugin_probe.wav"
    assert rm.get_asset_by_uuid("audio-plugin-test-uuid") is asset


def test_asset_plugin_registry_can_find_audio_by_extension() -> None:
    rm = ResourceManager()
    plugins = rm.asset_type_plugins.get_for_extension(".wav")

    assert len(plugins) == 1
    assert plugins[0].type_id == "audio_clip"


def test_asset_plugin_registry_can_find_texture_by_extension() -> None:
    rm = ResourceManager()
    plugins = rm.asset_type_plugins.get_for_extension(".png")

    assert len(plugins) == 1
    assert plugins[0].type_id == "texture"


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


def test_default_preloaders_use_plugin_adapter_for_audio() -> None:
    rm = ResourceManager()
    preloaders = create_default_preloaders(rm)
    audio_preloaders = [
        preloader
        for preloader in preloaders
        if ".wav" in preloader.extensions
    ]

    assert len(audio_preloaders) == 1
    assert isinstance(audio_preloaders[0], PluginPreLoader)
    assert audio_preloaders[0].resource_type == "audio_clip"


def test_default_preloaders_use_plugin_adapter_for_texture() -> None:
    rm = ResourceManager()
    preloaders = create_default_preloaders(rm)
    texture_preloaders = [
        preloader
        for preloader in preloaders
        if ".png" in preloader.extensions
    ]

    assert len(texture_preloaders) == 1
    assert isinstance(texture_preloaders[0], PluginPreLoader)
    assert texture_preloaders[0].resource_type == "texture"


def test_default_preloaders_use_plugin_adapter_for_glsl_shader_material_pipelines() -> None:
    rm = ResourceManager()
    preloaders = create_default_preloaders(rm)

    by_resource_type = {
        preloader.resource_type: preloader
        for preloader in preloaders
        if preloader.resource_type in {"glsl", "shader", "material", "pipeline", "scene_pipeline"}
    }

    assert set(by_resource_type.keys()) == {"glsl", "shader", "material", "pipeline", "scene_pipeline"}
    assert isinstance(by_resource_type["glsl"], PluginPreLoader)
    assert isinstance(by_resource_type["shader"], PluginPreLoader)
    assert isinstance(by_resource_type["material"], PluginPreLoader)
    assert isinstance(by_resource_type["pipeline"], PluginPreLoader)
    assert isinstance(by_resource_type["scene_pipeline"], PluginPreLoader)
