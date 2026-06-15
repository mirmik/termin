from pathlib import Path

import numpy as np

from termin.assets.resources import ResourceManager
from termin.editor_core.default_preloaders import create_default_preloaders
from termin.assets.plugin_preloader import PluginPreLoader
from termin_assets import PreLoadResult


def test_mesh_register_file_uses_asset_plugin(tmp_path) -> None:
    mesh_path = tmp_path / "plugin_probe.obj"
    mesh_path.write_text("", encoding="utf-8")
    rm = ResourceManager()
    result = PreLoadResult(
        resource_type="mesh",
        path=str(mesh_path),
        content=None,
        uuid="mesh-plugin-test-uuid",
        spec_data={"uuid": "mesh-plugin-test-uuid", "scale": 2.0},
    )

    rm.register_file(result)

    asset = rm.get_mesh_asset("plugin_probe")
    assert asset is not None
    assert asset.uuid == "mesh-plugin-test-uuid"
    assert asset.source_path is not None
    assert isinstance(asset.source_path, Path)
    assert str(asset.source_path) == str(mesh_path)
    asset.mark_just_saved()
    assert not asset.should_reload_from_file()
    assert rm.get_asset_by_uuid("mesh-plugin-test-uuid") is asset


def test_mesh_reload_updates_existing_tc_mesh_data(tmp_path) -> None:
    mesh_path = tmp_path / "scaled.obj"
    mesh_path.write_text(
        "\n".join(
            [
                "v 0 0 0",
                "v 1 0 0",
                "v 0 1 0",
                "f 1 2 3",
            ]
        ),
        encoding="utf-8",
    )

    rm = ResourceManager()
    result = PreLoadResult(
        resource_type="mesh",
        path=str(mesh_path),
        content=None,
        uuid="mesh-reload-existing-tc-mesh",
        spec_data={"uuid": "mesh-reload-existing-tc-mesh", "scale": 1.0},
    )
    rm.register_file(result)

    asset = rm.get_mesh_asset("scaled")
    assert asset is not None
    original_mesh = asset.data
    assert original_mesh is not None
    assert original_mesh.is_valid
    original_mesh_version = original_mesh.version
    np.testing.assert_allclose(
        np.asarray(original_mesh.vertices),
        np.asarray(
            [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float32,
        ),
    )

    rm.reload_file(
        PreLoadResult(
            resource_type="mesh",
            path=str(mesh_path),
            content=None,
            uuid="mesh-reload-existing-tc-mesh",
            spec_data={"uuid": "mesh-reload-existing-tc-mesh", "scale": 2.0},
        )
    )

    reloaded_mesh = asset.data
    assert reloaded_mesh is not None
    assert reloaded_mesh.is_valid
    assert reloaded_mesh.uuid == original_mesh.uuid
    assert reloaded_mesh.version > original_mesh_version
    np.testing.assert_allclose(
        np.asarray(reloaded_mesh.vertices),
        np.asarray(
            [
                [0.0, 0.0, 0.0],
                [2.0, 0.0, 0.0],
                [0.0, 0.0, 2.0],
            ],
            dtype=np.float32,
        ),
    )


def test_asset_plugin_registry_can_find_mesh_by_extension() -> None:
    rm = ResourceManager()
    plugins = rm.asset_type_plugins.get_for_extension(".obj")

    assert len(plugins) == 1
    assert plugins[0].type_id == "mesh"


def test_resource_manager_runtime_asset_api_registers_mesh(tmp_path) -> None:
    from termin.assets.mesh_asset import MeshAsset

    mesh_path = tmp_path / "runtime_api_probe.obj"
    mesh_path.write_text("", encoding="utf-8")
    rm = ResourceManager()
    asset = MeshAsset(
        mesh_data=None,
        name="runtime_api_probe",
        source_path=mesh_path,
        uuid="runtime-api-mesh-uuid",
    )

    rm.register_runtime_asset("mesh", "runtime_api_probe", asset, source_path=str(mesh_path), uuid=asset.uuid)

    assert rm.get_runtime_asset("mesh", "runtime_api_probe") is asset
    assert rm.get_runtime_asset_by_uuid("mesh", "runtime-api-mesh-uuid") is asset
    assert rm.get_mesh_asset("runtime_api_probe") is asset


def test_resource_manager_runtime_asset_api_get_or_create_glsl(tmp_path) -> None:
    glsl_path = tmp_path / "runtime_api_probe.glsl"
    glsl_path.write_text("// probe\n", encoding="utf-8")
    rm = ResourceManager()

    asset = rm.get_or_create_runtime_asset(
        "glsl",
        "runtime_api_probe.glsl",
        source_path=str(glsl_path),
        uuid="runtime-api-glsl-uuid",
    )

    assert rm.get_runtime_asset("glsl", "runtime_api_probe.glsl") is asset
    assert rm.get_runtime_asset_by_uuid("glsl", "runtime-api-glsl-uuid") is asset
    assert rm.glsl.get_asset("runtime_api_probe.glsl") is asset


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
    assert asset.source_path == Path("/tmp/plugin_probe.wav")
    assert rm.get_asset_by_uuid("audio-plugin-test-uuid") is asset


def test_glb_register_file_creates_spec_child_assets() -> None:
    rm = ResourceManager()
    result = PreLoadResult(
        resource_type="glb",
        path="/tmp/robot.glb",
        content=None,
        uuid="glb-plugin-test-uuid",
        spec_data={
            "uuid": "glb-plugin-test-uuid",
            "resources": {
                "meshes": {"Body": "glb-mesh-child-uuid"},
                "skeletons": {"skeleton": "glb-skeleton-child-uuid"},
                "animations": {"Walk": "glb-animation-child-uuid"},
            },
        },
    )

    rm.register_file(result)

    glb_asset = rm.get_glb_asset("robot")
    assert glb_asset is not None
    assert glb_asset.uuid == "glb-plugin-test-uuid"
    assert glb_asset.source_path is not None
    assert glb_asset.source_path == Path("/tmp/robot.glb")
    assert rm.get_asset_by_uuid("glb-plugin-test-uuid") is glb_asset

    mesh_asset = rm.get_mesh_asset_by_uuid("glb-mesh-child-uuid")
    skeleton_asset = rm.get_skeleton_asset_by_uuid("glb-skeleton-child-uuid")
    animation_asset = rm.get_animation_clip_asset_by_uuid("glb-animation-child-uuid")

    assert mesh_asset is not None
    assert mesh_asset.name == "robot_Body"
    assert skeleton_asset is not None
    assert skeleton_asset.name == "robot_skeleton"
    assert animation_asset is not None
    assert animation_asset.name == "Walk"


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


def test_asset_plugin_registry_can_find_glb_by_extension() -> None:
    rm = ResourceManager()
    plugins = rm.asset_type_plugins.get_for_extension(".glb")

    assert len(plugins) == 1
    assert plugins[0].type_id == "glb"


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


def test_default_preloaders_use_plugin_adapter_for_migrated_assets() -> None:
    rm = ResourceManager()
    preloaders = create_default_preloaders(rm)

    migrated = {
        "glsl",
        "shader",
        "material",
        "pipeline",
        "scene_pipeline",
        "prefab",
        "navmesh",
        "voxel_grid",
        "ui",
        "glb",
    }
    by_resource_type = {
        preloader.resource_type: preloader
        for preloader in preloaders
        if preloader.resource_type in migrated
    }

    assert set(by_resource_type.keys()) == migrated
    for resource_type in migrated:
        assert isinstance(by_resource_type[resource_type], PluginPreLoader)
