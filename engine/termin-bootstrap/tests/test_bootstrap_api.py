import os
import subprocess
import sys
import textwrap
from pathlib import Path


_OVERLAY = Path(os.environ["TERMIN_PYTHON_OVERLAY"])
_LIFECYCLE_SCENARIOS = Path(__file__).with_name("bootstrap_lifecycle_scenarios.py")


def _python_command() -> list[str]:
    return [sys.executable, "--termin-overlay", str(_OVERLAY)]


def _run_python(code: str) -> None:
    subprocess.run(
        [*_python_command(), "-c", textwrap.dedent(code)],
        check=True,
    )


def _run_python_without_nanobind_leaks(
    code: str,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [*_python_command(), "-c", textwrap.dedent(code)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "nanobind: leaked" not in result.stderr
    return result


def test_compatible_bootstrap_lifecycle_scenarios_share_one_process():
    # Every scenario in this harness restores process-global bootstrap state.
    # Keeping them together avoids repeated interpreter and native import cost.
    subprocess.run(
        [*_python_command(), str(_LIFECYCLE_SCENARIOS)],
        check=True,
    )


# Import-side-effect contracts need their own pristine module graph and registry
# baseline, so these intentionally remain one child process per test.
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


def test_declaring_python_component_has_no_registry_side_effects():
    _run_python(
        """
        from termin.inspect import InspectRegistry
        from termin.scene import ComponentRegistry, PythonComponent

        components = ComponentRegistry.instance()
        inspect = InspectRegistry.instance()
        component_types_before = {info["name"] for info in components.list_info()}
        inspect_types_before = set(inspect.types())

        class ImportOnlyProbeComponent(PythonComponent):
            pass

        assert {info["name"] for info in components.list_info()} == component_types_before
        assert set(inspect.types()) == inspect_types_before
        assert not components.has("ImportOnlyProbeComponent")
        assert not inspect.has_type("ImportOnlyProbeComponent")
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


# These contracts intentionally keep separate processes: the interpreter's
# nanobind shutdown diagnostics are part of each individual assertion.
def test_component_registry_names_survive_repeated_player_rebootstrap():
    _run_python_without_nanobind_leaks(
        """
        import gc

        from termin.bootstrap import bootstrap_player, shutdown_player
        from termin.scene import ComponentRegistry, Entity

        for iteration in range(3):
            bootstrap_player()

            registry = ComponentRegistry.instance()
            component_infos = registry.list_info()
            component_names = {info["name"] for info in component_infos}
            assert "CameraComponent" in component_names
            assert "PrefabInstanceState" in component_names

            camera_info = registry.get_info("CameraComponent")
            assert camera_info["name"] == "CameraComponent"
            assert camera_info["kind"] == "cxx"
            assert camera_info["is_abstract"] is False

            entity = Entity(f"component-registry-rebootstrap-{iteration}")
            component = entity.add_component_by_name("CameraComponent")
            assert component.type_name == "CameraComponent"
            assert entity.has_component_type("CameraComponent")

            prefab_state = entity.add_component_by_name("PrefabInstanceState")
            assert prefab_state.type_name == "PrefabInstanceState"
            assert entity.has_component_type("PrefabInstanceState")

            del prefab_state
            del component
            del entity
            gc.collect()
            shutdown_player()
            assert not registry.has("CameraComponent")
            assert not registry.has("PrefabInstanceState")
        """
    )


def test_builtin_bootstrap_registers_each_component_once():
    result = _run_python_without_nanobind_leaks(
        """
        from termin.bootstrap import bootstrap_player, shutdown_player

        for _ in range(3):
            bootstrap_player()
            shutdown_player()
        """
    )

    output = result.stdout + result.stderr
    assert "Ignoring unowned component registration for existing type" not in output
    assert "Ignoring unowned field registration for existing field" not in output


def test_explicit_component_publication_is_repeatable_after_rebootstrap():
    _run_python_without_nanobind_leaks(
        """
        import gc

        from termin.bootstrap import bootstrap_player, shutdown_player
        from termin.inspect import InspectField, InspectRegistry
        from termin.scene import (
            ComponentRegistry,
            Entity,
            PythonComponent,
            publish_python_component,
        )

        bootstrap_player()

        class RebootstrapProbeComponent(PythonComponent):
            component_category = "Regression"
            component_display_name = "Rebootstrap Probe"
            inspect_fields = {
                "value": InspectField(path="value", label="Value", kind="int"),
            }

            def __init__(self):
                super().__init__()
                self.value = 17

        assert not ComponentRegistry.instance().has("RebootstrapProbeComponent")
        publish_python_component(RebootstrapProbeComponent)

        shutdown_player()

        for iteration in range(3):
            bootstrap_player()
            assert not ComponentRegistry.instance().has("RebootstrapProbeComponent")
            publish_python_component(RebootstrapProbeComponent)
            registry = ComponentRegistry.instance()
            assert registry.has("RebootstrapProbeComponent")
            info = registry.get_info("RebootstrapProbeComponent")
            assert info["category"] == "Regression", info
            assert info["display_name"] == "Rebootstrap Probe", info
            assert "value" in {
                field.path for field in InspectRegistry.instance().fields("RebootstrapProbeComponent")
            }

            entity = Entity(f"rebootstrap-probe-{iteration}")
            entity.add_component_by_name("RebootstrapProbeComponent")
            component = entity.get_python_component("RebootstrapProbeComponent")
            assert isinstance(component, RebootstrapProbeComponent)
            component.value = 100 + iteration
            serialized = entity.serialize()
            component_data = serialized["components"][0]["data"]
            assert component_data["value"] == 100 + iteration
            del component
            del entity
            gc.collect()

            shutdown_player()
            assert not registry.has("RebootstrapProbeComponent")
        """
    )


def test_player_bootstrap_publishes_builtin_type_projections_once():
    result = _run_python_without_nanobind_leaks(
        """
        from termin.bootstrap import bootstrap_player, shutdown_player
        from termin.render_framework import tc_pass_registry_get_class
        from termin.scene import ComponentRegistry

        for _ in range(3):
            bootstrap_player()

            from termin.mesh import MeshComponent
            from termin.render import DrawableComponent
            from termin.render_passes import UIWidgetPass

            registry = ComponentRegistry.instance()
            assert registry.get_class("DrawableComponent") is DrawableComponent
            assert registry.get_class("MeshComponent") is MeshComponent
            assert registry.get_info("DrawableComponent")["category"] == "Rendering"
            assert tc_pass_registry_get_class("UIWidgetPass") is UIWidgetPass

            shutdown_player()
            assert not registry.has("DrawableComponent")
            assert registry.get_class("DrawableComponent") is None
            assert tc_pass_registry_get_class("UIWidgetPass") is None
        """
    )

    output = result.stdout + result.stderr
    assert "registration for existing type 'DrawableComponent'" not in output
    assert "explicit descriptor publication failed" not in output


def test_player_bootstrap_restores_preimported_python_pass_parent_first():
    _run_python_without_nanobind_leaks(
        """
        import termin.bootstrap
        import termin.render_framework.python_pass  # noqa: F401
        from termin.render_framework import tc_pass_registry_has

        termin.bootstrap.bootstrap_runtime()
        termin.bootstrap.shutdown_runtime()

        termin.bootstrap.bootstrap_player()
        assert tc_pass_registry_has("PythonFramePass")
        assert tc_pass_registry_has("HighlightPass")
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
