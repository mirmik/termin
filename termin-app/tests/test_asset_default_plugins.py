from termin_assets.default_plugins import (
    build_import_plugin_extension_map,
    register_default_import_asset_plugins,
    register_default_runtime_asset_plugins,
)
from termin_assets import AssetTypeRegistry


def test_default_plugins_register_runtime_and_import_sides_separately() -> None:
    registry = AssetTypeRegistry()

    register_default_runtime_asset_plugins(registry)

    assert registry.get_runtime("texture") is not None
    assert registry.get_runtime("mesh") is not None
    assert registry.get_runtime("audio_clip") is not None
    assert registry.get_runtime("glsl") is not None
    assert registry.get_runtime("shader") is not None
    assert registry.get_runtime("material") is not None
    assert registry.get_runtime("pipeline") is not None
    assert registry.get_runtime("scene_pipeline") is not None
    assert registry.get_runtime("prefab") is not None
    assert registry.get_runtime("navmesh") is not None
    assert registry.get_runtime("voxel_grid") is not None
    assert registry.get_runtime("ui") is not None
    assert registry.get_runtime("glb") is not None
    assert registry.get_import("texture") is None

    register_default_import_asset_plugins(registry)

    assert registry.get_import("texture") is not None
    assert registry.get_import("mesh") is not None
    assert registry.get_import("audio_clip") is not None
    assert registry.get_import("glsl") is not None
    assert registry.get_import("shader") is not None
    assert registry.get_import("material") is not None
    assert registry.get_import("pipeline") is not None
    assert registry.get_import("scene_pipeline") is not None
    assert registry.get_import("prefab") is not None
    assert registry.get_import("navmesh") is not None
    assert registry.get_import("voxel_grid") is not None
    assert registry.get_import("ui") is not None
    assert registry.get_import("glb") is not None


def test_default_import_plugin_extension_map_uses_plugin_type_ids() -> None:
    registry = AssetTypeRegistry()
    register_default_import_asset_plugins(registry)

    extension_map = build_import_plugin_extension_map(registry)

    assert extension_map[".png"].type_id == "texture"
    assert extension_map[".obj"].type_id == "mesh"
    assert extension_map[".wav"].type_id == "audio_clip"
    assert extension_map[".glsl"].type_id == "glsl"
    assert extension_map[".shader"].type_id == "shader"
    assert extension_map[".material"].type_id == "material"
    assert extension_map[".pipeline"].type_id == "pipeline"
    assert extension_map[".scene_pipeline"].type_id == "scene_pipeline"
    assert extension_map[".prefab"].type_id == "prefab"
    assert extension_map[".navmesh"].type_id == "navmesh"
    assert extension_map[".voxels"].type_id == "voxel_grid"
    assert extension_map[".uiscript"].type_id == "ui"
    assert extension_map[".glb"].type_id == "glb"
    assert extension_map[".gltf"].type_id == "glb"


def test_render_pipeline_asset_legacy_paths_reexport_canonical_classes() -> None:
    from termin.assets.pipeline_asset import PipelineAsset as AppPipelineAsset
    from termin.assets.pipeline_plugin import PipelineImportPlugin as AppPipelineImportPlugin
    from termin.assets.scene_pipeline_asset import ScenePipelineAsset as AppScenePipelineAsset
    from termin.assets.scene_pipeline_plugin import (
        ScenePipelineImportPlugin as AppScenePipelineImportPlugin,
    )
    from termin.default_assets.render.pipeline_asset import PipelineAsset
    from termin.default_assets.render.pipeline_plugin import PipelineImportPlugin
    from termin.default_assets.render.scene_pipeline_asset import ScenePipelineAsset
    from termin.default_assets.render.scene_pipeline_plugin import ScenePipelineImportPlugin

    assert AppPipelineAsset is PipelineAsset
    assert AppPipelineImportPlugin is PipelineImportPlugin
    assert AppScenePipelineAsset is ScenePipelineAsset
    assert AppScenePipelineImportPlugin is ScenePipelineImportPlugin
