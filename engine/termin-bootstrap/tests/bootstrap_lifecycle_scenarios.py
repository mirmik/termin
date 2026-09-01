"""Compatible bootstrap lifecycle contracts executed in one child process."""

from collections.abc import Callable
import sys
import traceback


def player_imports_default_python_render_passes() -> None:
    import termin.bootstrap

    assert "termin.render_passes" not in sys.modules
    try:
        termin.bootstrap.bootstrap_player()
        assert "termin.render_passes" in sys.modules
    finally:
        termin.bootstrap.shutdown_player()


def runtime_bootstrap_registers_core_resource_kinds() -> None:
    import termin.bootstrap
    from termin.inspect import KindRegistry

    try:
        termin.bootstrap.register_runtime_kinds(
            mesh=True,
            material=True,
            skeleton=False,
            animation=False,
            voxel_grid=False,
            navmesh=False,
            entity=False,
        )

        kinds = set(KindRegistry.instance().kinds())
        assert "tc_mesh" in kinds
        assert "tc_material" in kinds
    finally:
        termin.bootstrap.shutdown_runtime()


def bootstrap_configures_resource_manager_factory() -> None:
    import termin.bootstrap
    from termin_assets import get_resource_manager

    marker = object()
    assert get_resource_manager() is None

    try:
        termin.bootstrap.configure_resource_manager_factory(lambda: marker)
        assert get_resource_manager() is marker
    finally:
        termin.bootstrap.configure_resource_manager_factory(None)
    assert get_resource_manager() is None


def runtime_bootstrap_registers_component_base_fields() -> None:
    import termin.bootstrap
    from termin.inspect import InspectRegistry

    registry = InspectRegistry.instance()
    before = {field.path for field in registry.fields("Component")}
    assert "display_name" not in before
    assert "enabled" not in before

    try:
        termin.bootstrap.bootstrap_runtime()
        after = {field.path for field in registry.fields("Component")}
        assert "display_name" in after
        assert "enabled" in after
    finally:
        termin.bootstrap.shutdown_runtime()


def domain_native_kind_registration_functions_remain_available() -> None:
    import termin.bootstrap
    import termin.animation._animation_native as animation_native
    import termin.navmesh._navmesh_native as navmesh_native
    import termin.skeleton._skeleton_native as skeleton_native
    import termin.voxels._voxels_native as voxels_native
    from termin.inspect import KindRegistry

    try:
        animation_native.register_animation_kind_handlers()
        navmesh_native.register_navmesh_kind_handlers()
        skeleton_native.register_tc_skeleton_kind()
        voxels_native.register_voxel_grid_kind_handlers()

        registry = KindRegistry.instance()
        kinds = set(registry.kinds())
        assert "tc_animation_clip" in kinds
        assert "navmesh_handle" in kinds
        assert "tc_skeleton" in kinds
        assert "voxel_grid_handle" in kinds
        assert registry.kind_for_object(animation_native.TcAnimationClip()) == "tc_animation_clip"
        assert registry.kind_for_object(navmesh_native.TcNavMesh()) == "navmesh_handle"
        assert registry.kind_for_object(skeleton_native.TcSkeleton()) == "tc_skeleton"
        assert registry.kind_for_object(voxels_native.TcVoxelGrid()) == "voxel_grid_handle"
    finally:
        termin.bootstrap.shutdown_runtime()


def player_bootstrap_registers_python_type_mappings() -> None:
    import termin.bootstrap
    import termin.mesh
    from termin.inspect import KindRegistry
    from termin.materials import TcMaterial

    try:
        termin.bootstrap.init_python_kind_handlers(
            mesh=True,
            material=True,
            skeleton=False,
            animation=False,
            voxel_grid=False,
            navmesh=False,
            entity=False,
        )

        registry = KindRegistry.instance()
        assert registry.kind_for_object(termin.mesh.TcMesh()) == "tc_mesh"
        assert registry.kind_for_object(TcMaterial()) == "tc_material"
    finally:
        termin.bootstrap.shutdown_runtime()


def partial_kind_init_allows_later_full_player_bootstrap() -> None:
    import termin.bootstrap
    from termin.inspect import KindRegistry

    termin.bootstrap.init_python_kind_handlers(
        mesh=True,
        material=True,
        skeleton=False,
        animation=False,
        voxel_grid=False,
        navmesh=False,
        entity=False,
    )

    try:
        termin.bootstrap.bootstrap_player()
        from termin.skeleton import TcSkeleton

        registry = KindRegistry.instance()
        assert registry.kind_for_object(TcSkeleton()) == "tc_skeleton"
    finally:
        termin.bootstrap.shutdown_player()


def player_bootstrap_restores_loaded_passes_after_repeated_shutdown() -> None:
    from termin.bootstrap import bootstrap_player, shutdown_player
    from termin.inspect import InspectRegistry
    from termin.render_framework import tc_pass_registry_has
    from termin.render_passes import UIWidgetPass  # noqa: F401

    for _ in range(3):
        try:
            bootstrap_player()
            assert tc_pass_registry_has("UIWidgetPass")
            fields = {field.path for field in InspectRegistry.instance().fields("UIWidgetPass")}
            assert "include_scene_entities" in fields
            assert "include_internal_entities" in fields
        finally:
            shutdown_player()
        assert not tc_pass_registry_has("UIWidgetPass")


def player_bootstrap_registers_builtin_component_types() -> None:
    import termin.bootstrap
    from termin.inspect import InspectRegistry, KindRegistry
    from termin.scene import ComponentRegistry

    components = ComponentRegistry.instance()
    assert not components.has("MeshComponent")
    assert not components.has("CameraComponent")

    try:
        termin.bootstrap.bootstrap_player()

        required = {
            "UnknownComponent",
            "MeshComponent",
            "ColliderComponent",
            "KinematicUnitComponent",
            "CameraComponent",
            "MeshRenderer",
            "FoliageLayerComponent",
            "SkeletonController",
            "UIComponent",
        }
        missing = {name for name in required if not components.has(name)}
        assert not missing

        inspect = InspectRegistry.instance()
        assert "mesh" in {field.path for field in inspect.fields("MeshComponent")}
        assert "fov_x_degrees" in {field.path for field in inspect.fields("CameraComponent")}
        assert "material" in {field.path for field in inspect.fields("MeshRenderer")}
        assert "foliage" in {field.path for field in inspect.fields("FoliageLayerComponent")}
        ui_fields = {field.path: field for field in inspect.fields("UIComponent")}
        assert ui_fields["ui_layout"].kind == "ui_document"
        assert {"priority", "input_source_mask"} <= set(ui_fields)
        assert "foliage_data_handle" in set(KindRegistry.instance().kinds())
        assert "ui_document" in set(KindRegistry.instance().kinds())
    finally:
        termin.bootstrap.shutdown_player()


def player_shutdown_cleans_python_and_render_globals() -> None:
    import termin.bootstrap

    termin.bootstrap.bootstrap_player()

    from termin.render_framework import (
        PythonFramePass,
        tc_pass_registry_has,
        tc_pipeline_create,
        tc_pipeline_registry_count,
    )
    from termin.scene import ComponentRegistry, PythonComponent, publish_python_component

    class BootstrapShutdownPass(PythonFramePass):
        def execute(self, ctx):
            pass

    class BootstrapShutdownComponent(PythonComponent):
        pass

    assert not ComponentRegistry.instance().has("BootstrapShutdownComponent")
    publish_python_component(BootstrapShutdownComponent)
    tc_pipeline_create("bootstrap-shutdown-test")

    assert tc_pass_registry_has("BootstrapShutdownPass")
    assert ComponentRegistry.instance().has("BootstrapShutdownComponent")
    assert tc_pipeline_registry_count() == 1

    termin.bootstrap.shutdown_player()

    assert not tc_pass_registry_has("BootstrapShutdownPass")
    assert not ComponentRegistry.instance().has("BootstrapShutdownComponent")
    assert tc_pipeline_registry_count() == 0
    termin.bootstrap.shutdown_player()


def runtime_shutdown_allows_later_rebootstrap() -> None:
    import termin.bootstrap
    from termin.inspect import KindRegistry

    try:
        termin.bootstrap.bootstrap_player()
        assert "tc_mesh" in set(KindRegistry.instance().kinds())

        termin.bootstrap.shutdown_player()
        assert "tc_mesh" not in set(KindRegistry.instance().kinds())

        termin.bootstrap.bootstrap_player()
        assert "tc_mesh" in set(KindRegistry.instance().kinds())
    finally:
        termin.bootstrap.shutdown_player()


def default_textures_follow_native_registry_lifecycle() -> None:
    from termin.bootstrap import bootstrap_player, shutdown_player
    from termin.render.texture import get_white_texture
    from termin.render.texture_handle import (
        get_normal_texture_handle,
        get_white_texture_handle,
    )
    from termin.graphics import TcTexture

    try:
        bootstrap_player()
        old_white = get_white_texture_handle()
        old_normal = get_normal_texture_handle()
        assert old_white.is_valid
        assert old_normal.is_valid

        first_wrapper = get_white_texture()
        second_wrapper = get_white_texture()
        assert first_wrapper is not second_wrapper
        assert first_wrapper.texture_data is not second_wrapper.texture_data

        shutdown_player()
        assert not old_white.is_valid
        assert not old_normal.is_valid

        bootstrap_player()
        new_white = get_white_texture_handle()
        new_normal = get_normal_texture_handle()
        assert new_white.is_valid
        assert new_normal.is_valid
        assert not old_white.is_valid
        assert not old_normal.is_valid
        assert TcTexture.from_uuid("__white_1x1__").is_valid
        assert TcTexture.from_uuid("__normal_1x1__").is_valid
    finally:
        shutdown_player()


_SCENARIOS: tuple[tuple[str, Callable[[], None]], ...] = (
    ("player imports default Python render passes", player_imports_default_python_render_passes),
    ("runtime registers core resource kinds", runtime_bootstrap_registers_core_resource_kinds),
    ("resource manager factory", bootstrap_configures_resource_manager_factory),
    ("runtime registers Component fields", runtime_bootstrap_registers_component_base_fields),
    (
        "domain native kind registration functions",
        domain_native_kind_registration_functions_remain_available,
    ),
    ("player registers Python type mappings", player_bootstrap_registers_python_type_mappings),
    ("partial kind init then full player", partial_kind_init_allows_later_full_player_bootstrap),
    (
        "loaded Python passes survive rebootstrap",
        player_bootstrap_restores_loaded_passes_after_repeated_shutdown,
    ),
    ("builtin component types", player_bootstrap_registers_builtin_component_types),
    ("player shutdown cleans globals", player_shutdown_cleans_python_and_render_globals),
    ("runtime rebootstrap", runtime_shutdown_allows_later_rebootstrap),
    ("default texture lifecycle", default_textures_follow_native_registry_lifecycle),
)


def main() -> int:
    for name, scenario in _SCENARIOS:
        try:
            scenario()
        except BaseException:
            print(f"bootstrap lifecycle scenario failed: {name}", file=sys.stderr)
            traceback.print_exc()
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
