import subprocess
import sys
import textwrap


def _run_python(code: str) -> None:
    subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        check=True,
    )


def _run_python_without_nanobind_leaks(code: str) -> None:
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "nanobind: leaked" not in result.stderr


def test_importing_bootstrap_has_no_kind_registration_side_effects():
    _run_python(
        """
        from termin.inspect import KindRegistry

        before = set(KindRegistry.instance().kinds())
        import termin.bootstrap  # noqa: F401
        after = set(KindRegistry.instance().kinds())

        assert after == before
        """
    )


def test_importing_bootstrap_has_no_component_registration_side_effects():
    _run_python(
        """
        from termin.scene import ComponentRegistry

        registry = ComponentRegistry.instance()
        before = set(registry.list_native())
        import termin.bootstrap  # noqa: F401
        after = set(registry.list_native())

        assert after == before
        assert "MeshComponent" not in after
        assert "CameraComponent" not in after
        """
    )


def test_importing_domain_native_modules_has_no_kind_registration_side_effects():
    _run_python(
        """
        from termin.inspect import KindRegistry

        before = set(KindRegistry.instance().kinds())

        import termin.animation._animation_native  # noqa: F401
        import termin.navmesh._navmesh_native  # noqa: F401
        import termin.skeleton._skeleton_native  # noqa: F401
        import termin.voxels._voxels_native  # noqa: F401

        after = set(KindRegistry.instance().kinds())
        assert after == before
        """
    )


def test_legacy_app_native_module_is_removed():
    _run_python(
        """
        import importlib

        try:
            importlib.import_module("termin._native")
        except ModuleNotFoundError:
            pass
        else:
            raise AssertionError("termin._native should not be importable")
        """
    )


def test_explicit_runtime_bootstrap_registers_core_resource_kinds():
    _run_python(
        """
        import termin.bootstrap
        from termin.inspect import KindRegistry

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
        """
    )


def test_explicit_bootstrap_configures_resource_manager_factory():
    _run_python(
        """
        import termin.bootstrap
        from termin_assets import get_resource_manager

        marker = object()
        assert get_resource_manager() is None

        termin.bootstrap.configure_resource_manager_factory(lambda: marker)
        assert get_resource_manager() is marker

        termin.bootstrap.configure_resource_manager_factory(None)
        assert get_resource_manager() is None
        """
    )


def test_explicit_inspect_bootstrap_registers_component_base_fields():
    _run_python(
        """
        import termin.bootstrap
        from termin.inspect import InspectRegistry

        registry = InspectRegistry.instance()
        before = {field.path for field in registry.fields("Component")}
        assert "display_name" not in before
        assert "enabled" not in before

        termin.bootstrap.init_inspect_adapters()

        after = {field.path for field in registry.fields("Component")}
        assert "display_name" in after
        assert "enabled" in after
        """
    )


def test_explicit_domain_native_kind_registration_functions_remain_available():
    _run_python(
        """
        from termin.inspect import KindRegistry
        import termin.animation._animation_native as animation_native
        import termin.navmesh._navmesh_native as navmesh_native
        import termin.skeleton._skeleton_native as skeleton_native
        import termin.voxels._voxels_native as voxels_native

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
        """
    )


def test_explicit_player_bootstrap_registers_python_type_mappings():
    _run_python(
        """
        import termin.bootstrap
        import tmesh
        from termin.inspect import KindRegistry
        from termin.materials import TcMaterial

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
        assert registry.kind_for_object(tmesh.TcMesh()) == "tc_mesh"
        assert registry.kind_for_object(TcMaterial()) == "tc_material"
        """
    )


def test_partial_python_kind_init_does_not_block_later_full_player_bootstrap():
    _run_python(
        """
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

        termin.bootstrap.bootstrap_player()

        from termin.skeleton import TcSkeleton

        registry = KindRegistry.instance()
        assert registry.kind_for_object(TcSkeleton()) == "tc_skeleton"
        """
    )


def test_player_bootstrap_imports_default_python_render_passes():
    _run_python(
        """
        import sys
        import termin.bootstrap

        assert "termin.render_passes" not in sys.modules

        termin.bootstrap.bootstrap_player()

        assert "termin.render_passes" in sys.modules
        """
    )


def test_player_bootstrap_registers_builtin_component_types():
    _run_python(
        """
        import termin.bootstrap
        from termin.inspect import InspectRegistry, KindRegistry
        from termin.scene import ComponentRegistry

        components = ComponentRegistry.instance()
        assert not components.has("MeshComponent")
        assert not components.has("CameraComponent")

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
        }
        missing = {name for name in required if not components.has(name)}
        assert not missing

        inspect = InspectRegistry.instance()
        assert "mesh" in {field.path for field in inspect.fields("MeshComponent")}
        assert "fov_x_degrees" in {field.path for field in inspect.fields("CameraComponent")}
        assert "material" in {field.path for field in inspect.fields("MeshRenderer")}
        assert "foliage" in {field.path for field in inspect.fields("FoliageLayerComponent")}
        assert "foliage_data_handle" in set(KindRegistry.instance().kinds())
        """
    )


def test_player_shutdown_cleans_python_and_render_globals():
    _run_python(
        """
        import termin.bootstrap

        termin.bootstrap.bootstrap_player()

        from termin.render_framework import (
            PythonFramePass,
            tc_pass_registry_has,
            tc_pipeline_create,
            tc_pipeline_registry_count,
        )
        from termin.scene import ComponentRegistry, PythonComponent

        class BootstrapShutdownPass(PythonFramePass):
            def execute(self, ctx):
                pass

        class BootstrapShutdownComponent(PythonComponent):
            pass

        tc_pipeline_create("bootstrap-shutdown-test")

        assert tc_pass_registry_has("BootstrapShutdownPass")
        assert ComponentRegistry.instance().has("BootstrapShutdownComponent")
        assert tc_pipeline_registry_count() == 1

        termin.bootstrap.shutdown_player()

        assert not tc_pass_registry_has("BootstrapShutdownPass")
        assert not ComponentRegistry.instance().has("BootstrapShutdownComponent")
        assert tc_pipeline_registry_count() == 0

        termin.bootstrap.shutdown_player()
        """
    )


def test_runtime_shutdown_allows_later_rebootstrap():
    _run_python(
        """
        import termin.bootstrap
        from termin.inspect import KindRegistry

        termin.bootstrap.bootstrap_player()
        assert "tc_mesh" in set(KindRegistry.instance().kinds())

        termin.bootstrap.shutdown_player()
        assert "tc_mesh" not in set(KindRegistry.instance().kinds())

        termin.bootstrap.bootstrap_player()
        assert "tc_mesh" in set(KindRegistry.instance().kinds())

        termin.bootstrap.shutdown_player()
        """
    )


def test_player_shutdown_releases_standalone_entity_components():
    _run_python_without_nanobind_leaks(
        """
        import termin.bootstrap
        from termin.mesh import MeshComponent
        from termin.scene import Entity

        for iteration in range(2):
            termin.bootstrap.bootstrap_player()
            entity = Entity(f"standalone-shutdown-{iteration}")
            component = MeshComponent()
            entity.add_component(component)
            del component
            del entity
            termin.bootstrap.shutdown_player()
        """
    )
