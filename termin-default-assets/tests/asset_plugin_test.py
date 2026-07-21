from pathlib import Path

import numpy as np

from termin.default_assets.resource_manager import DefaultResourceManager
from termin.default_assets.default_preloaders import create_default_preloaders
from termin_assets.plugin_preloader import PluginPreLoader
from termin_assets import PreLoadResult, get_resource_manager, set_resource_manager_factory


def test_resource_manager_reset_restores_process_factory() -> None:
    set_resource_manager_factory(None)

    DefaultResourceManager._reset_for_testing()
    rm = DefaultResourceManager.instance()

    try:
        assert get_resource_manager() is rm
    finally:
        DefaultResourceManager.shutdown_instance()


def test_mesh_register_file_uses_asset_plugin(tmp_path) -> None:
    mesh_path = tmp_path / "plugin_probe.obj"
    mesh_path.write_text("", encoding="utf-8")
    rm = DefaultResourceManager()
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

    rm = DefaultResourceManager()
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


def test_asset_plugin_registry_can_find_default_import_plugins_by_extension() -> None:
    rm = DefaultResourceManager()
    expected_types = {
        ".obj": "mesh",
        ".wav": "audio_clip",
        ".ogg": "audio_clip",
        ".png": "texture",
        ".glb": "glb",
    }

    for extension, type_id in expected_types.items():
        plugins = rm.asset_type_plugins.get_for_extension(extension)
        assert len(plugins) == 1
        assert plugins[0].type_id == type_id


def test_resource_manager_runtime_asset_api_registers_mesh(tmp_path) -> None:
    from termin.default_assets.mesh.asset import MeshAsset

    mesh_path = tmp_path / "runtime_api_probe.obj"
    mesh_path.write_text("", encoding="utf-8")
    rm = DefaultResourceManager()
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


def test_audio_clip_register_file_uses_asset_plugin() -> None:
    rm = DefaultResourceManager()
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
    rm = DefaultResourceManager()
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
    assert mesh_asset.embedded_parent is glb_asset
    assert mesh_asset.embedded_parent_key == "Body"
    assert skeleton_asset is not None
    assert skeleton_asset.name == "robot_skeleton"
    assert skeleton_asset.embedded_parent is glb_asset
    assert skeleton_asset.embedded_parent_key == "skeleton"
    assert animation_asset is not None
    assert animation_asset.name == "robot_Walk"
    assert animation_asset.embedded_parent is glb_asset
    assert animation_asset.embedded_parent_key == "Walk"


def test_glb_animation_child_asset_names_are_scoped_by_parent_glb() -> None:
    rm = DefaultResourceManager()

    rm.register_file(
        PreLoadResult(
            resource_type="glb",
            path="/tmp/robot.glb",
            content=None,
            uuid="glb-robot-uuid",
            spec_data={
                "uuid": "glb-robot-uuid",
                "resources": {
                    "animations": {"Walk": "glb-robot-walk-uuid"},
                },
            },
        )
    )
    rm.register_file(
        PreLoadResult(
            resource_type="glb",
            path="/tmp/guard.glb",
            content=None,
            uuid="glb-guard-uuid",
            spec_data={
                "uuid": "glb-guard-uuid",
                "resources": {
                    "animations": {"Walk": "glb-guard-walk-uuid"},
                },
            },
        )
    )

    robot_glb = rm.get_glb_asset("robot")
    guard_glb = rm.get_glb_asset("guard")
    robot_walk = rm.get_animation_clip_asset_by_uuid("glb-robot-walk-uuid")
    guard_walk = rm.get_animation_clip_asset_by_uuid("glb-guard-walk-uuid")

    assert robot_glb is not None
    assert guard_glb is not None
    assert robot_walk is not None
    assert guard_walk is not None
    assert robot_walk is not guard_walk
    assert robot_walk.name == "robot_Walk"
    assert guard_walk.name == "guard_Walk"
    assert robot_walk.embedded_parent is robot_glb
    assert guard_walk.embedded_parent is guard_glb
    assert robot_walk.embedded_parent_key == "Walk"
    assert guard_walk.embedded_parent_key == "Walk"
    assert rm.get_animation_clip_asset("robot_Walk") is robot_walk
    assert rm.get_animation_clip_asset("guard_Walk") is guard_walk


def test_default_preloaders_use_plugin_adapters_for_direct_asset_files() -> None:
    rm = DefaultResourceManager()
    preloaders = create_default_preloaders(rm)
    expected_types = {
        ".obj": "mesh",
        ".wav": "audio_clip",
        ".png": "texture",
    }

    for extension, type_id in expected_types.items():
        matching_preloaders = [
            preloader
            for preloader in preloaders
            if extension in preloader.extensions
        ]
        assert len(matching_preloaders) == 1
        assert isinstance(matching_preloaders[0], PluginPreLoader)
        assert matching_preloaders[0].resource_type == type_id


def test_default_preloaders_use_plugin_adapter_for_migrated_assets() -> None:
    rm = DefaultResourceManager()
    preloaders = create_default_preloaders(rm)

    migrated = {
        "shader",
        "material",
        "pipeline",
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


def test_glsl_is_not_a_default_authored_asset_type() -> None:
    rm = DefaultResourceManager()
    assert rm.asset_type_plugins.get_for_extension(".glsl") == []
    assert "glsl" not in dir(rm)
