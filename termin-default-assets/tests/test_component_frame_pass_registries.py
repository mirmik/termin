import sys
import types
from pathlib import Path

import pytest

from termin.default_assets.resource_manager import DefaultResourceManager
from termin.render_framework.frame_pass_registry import FramePassRegistry
from termin.scene.component_registry import ComponentClassRegistry


def test_component_class_registry_registers_builtin_specs() -> None:
    module = types.ModuleType("_termin_component_registry_test_module")

    class ProbeComponent:
        pass

    module.ProbeComponent = ProbeComponent
    sys.modules[module.__name__] = module
    try:
        registry = ComponentClassRegistry()
        registered = registry.register_builtins([(module.__name__, "ProbeComponent")])

        assert registered == ["ProbeComponent"]
        assert registry.get("ProbeComponent") is ProbeComponent
        assert registry.list_names() == ["ProbeComponent"]
    finally:
        sys.modules.pop(module.__name__, None)


def test_frame_pass_registry_registers_builtin_specs() -> None:
    module = types.ModuleType("_termin_frame_pass_registry_test_module")

    class ProbeFramePass:
        pass

    module.ProbeFramePass = ProbeFramePass
    sys.modules[module.__name__] = module
    try:
        registry = FramePassRegistry()
        registered = registry.register_builtins([(module.__name__, "ProbeFramePass")])

        assert registered == ["ProbeFramePass"]
        assert registry.get("ProbeFramePass") is ProbeFramePass
        assert registry.list_names() == ["ProbeFramePass"]
    finally:
        sys.modules.pop(module.__name__, None)


def test_resource_manager_delegates_component_and_frame_pass_facades() -> None:
    rm = DefaultResourceManager()

    class ProbeComponent:
        pass

    class ProbeFramePass:
        pass

    rm.register_component("ProbeComponent", ProbeComponent)
    rm.register_frame_pass("ProbeFramePass", ProbeFramePass)

    assert rm.component_registry.get("ProbeComponent") is ProbeComponent
    assert rm.components["ProbeComponent"] is ProbeComponent
    assert rm.get_component("ProbeComponent") is ProbeComponent
    assert rm.list_component_names() == ["ProbeComponent"]

    assert rm.frame_pass_registry.get("ProbeFramePass") is ProbeFramePass
    assert rm.frame_passes["ProbeFramePass"] is ProbeFramePass
    assert rm.get_frame_pass("ProbeFramePass") is ProbeFramePass
    assert rm.list_frame_pass_names() == ["ProbeFramePass"]
    assert "scan_components" not in dir(rm)
    assert "scan_frame_passes" not in dir(rm)


def test_module_owner_context_unregisters_python_component_registrations() -> None:
    import termin.bootstrap
    from termin.inspect import InspectField, InspectRegistry
    from termin.scene import ComponentRegistry, PythonComponent
    from termin_modules.module_context import (
        module_registration_context,
        publish_module_owner,
        unregister_module_owner,
    )

    termin.bootstrap.bootstrap_player()
    module_id = "owner_context_probe"
    component_name = "OwnerContextProbeComponent"
    component_registry = ComponentRegistry.instance()
    inspect_registry = InspectRegistry.instance()

    try:
        component_registry.unregister_python(component_name)
    except AttributeError:
        component_registry.unregister(component_name)
    inspect_registry.unregister_type(component_name)
    unregister_module_owner(module_id)

    try:
        with module_registration_context(module_id, [__name__]):
            class OwnerContextProbeComponent(PythonComponent):
                inspect_fields = {
                    "value": InspectField(path="value", label="Value", kind="int")
                }

                def __init__(self):
                    super().__init__()
                    self.value = 7

            publish_module_owner(module_id)

        assert component_registry.has(component_name)
        assert component_name in component_registry.list_owned(module_id)
        assert inspect_registry.has_type(component_name)

        unregister_module_owner(module_id)

        assert not component_registry.has(component_name)
        assert not inspect_registry.has_type(component_name)

        assert not component_registry.has(component_name)
    finally:
        unregister_module_owner(module_id)
        termin.bootstrap.shutdown_player()


def test_module_owner_context_marks_python_frame_pass_runtime_type() -> None:
    from termin.inspect import InspectRegistry, _inspect_native
    from termin.render_framework import (
        PythonFramePass,
        tc_pass_registry_has,
        tc_pass_registry_unregister_python,
    )
    from termin.render_framework.python_pass import register_loaded_python_passes
    from termin_modules.module_context import (
        module_registration_context,
        unregister_module_owner,
    )

    module_id = "owner_context_pass_probe"
    pass_name = "OwnerContextProbeFramePass"
    inspect_registry = InspectRegistry.instance()

    try:
        tc_pass_registry_unregister_python(pass_name)
    except Exception:
        pass
    inspect_registry.unregister_type(pass_name)
    register_loaded_python_passes()

    try:
        with module_registration_context(module_id, [__name__]):
            class OwnerContextProbeFramePass(PythonFramePass):
                pass

        records = {
            record["name"]: record
            for record in _inspect_native.runtime_type_registry_snapshot()
        }
        record = records[pass_name]
        assert record["owner"] == module_id
        assert "termin.render.frame_pass" in record["facets"]

        unregister_module_owner(module_id)
        records = {
            record["name"]: record
            for record in _inspect_native.runtime_type_registry_snapshot()
        }
        assert pass_name not in records
        assert not tc_pass_registry_has(pass_name)

        register_loaded_python_passes()
        assert not tc_pass_registry_has(pass_name)
    finally:
        tc_pass_registry_unregister_python(pass_name)
        inspect_registry.unregister_type(pass_name)
        unregister_module_owner(module_id)


def test_default_builtin_specs_live_below_app_layer() -> None:
    from termin.default_assets.builtin_types import (
        get_default_builtin_component_specs,
        get_default_builtin_frame_pass_specs,
    )

    component_specs = get_default_builtin_component_specs()
    frame_pass_specs = get_default_builtin_frame_pass_specs()

    assert ("termin.render_components", "CameraComponent") in component_specs
    assert ("termin.render_components", "CameraController") in component_specs
    assert ("termin.ui_components", "UIComponent") in component_specs
    assert ("termin.colliders.teleport_component", "TeleportComponent") in component_specs
    assert ("termin.render_passes", "HighlightPass") in frame_pass_specs
    assert ("termin.render_passes", "UIWidgetPass") in frame_pass_specs
    assert ("termin.render_components", "MaterialPass") in frame_pass_specs
    assert (
        "termin.visualization.render.framegraph.passes.ui_widget",
        "UIWidgetPass",
    ) not in frame_pass_specs


def test_default_builtin_specs_include_migrated_app_types() -> None:
    from termin.default_assets.builtin_types import (
        get_default_builtin_component_specs,
        get_default_builtin_frame_pass_specs,
    )

    component_specs = get_default_builtin_component_specs()
    frame_pass_specs = get_default_builtin_frame_pass_specs()

    assert ("termin.colliders.teleport_component", "TeleportComponent") in component_specs
    assert ("termin.render_components", "CameraComponent") in component_specs
    assert ("termin.render_components", "CameraController") in component_specs
    assert ("termin.ui_components", "UIComponent") in component_specs

    assert ("termin.render_passes", "UIWidgetPass") in frame_pass_specs
    assert ("termin.render_passes", "HighlightPass") in frame_pass_specs
    assert ("termin.render_passes", "ImmediateDepthPass") in frame_pass_specs
    assert ("termin.render_passes", "UnifiedGizmoPass") in frame_pass_specs
    assert ("termin.render_components", "MaterialPass") in frame_pass_specs


def test_ui_component_and_pass_use_canonical_paths() -> None:
    try:
        from termin.render_passes import UIWidgetPass
        from termin.ui_components import UIComponent

        assert UIWidgetPass.__module__ == "termin.render_passes.ui_widget"
        assert UIComponent.__module__ == "termin.ui_components.component"
    finally:
        from termin.inspect import InspectRegistry
        from termin.scene import ComponentRegistry

        ComponentRegistry.instance().unregister_python("UIComponent")
        InspectRegistry.instance().unregister_type("UIComponent")


def test_render_config_types_use_canonical_paths() -> None:
    from termin.render import (
        RenderTargetConfig,
        ViewportConfig,
        deserialize_render_target_config,
        deserialize_viewport_config,
        serialize_render_target_config,
        serialize_viewport_config,
    )

    viewport_config = ViewportConfig()
    viewport_config.name = "Main"
    assert serialize_viewport_config(viewport_config)["name"] == "Main"
    assert deserialize_viewport_config({"name": "Main"}).name == "Main"

    render_target_config = RenderTargetConfig()
    render_target_config.name = "Target"
    assert serialize_render_target_config(render_target_config)["name"] == "Target"
    assert deserialize_render_target_config({"name": "Target"}).name == "Target"


def test_legacy_ui_component_and_pass_paths_are_removed() -> None:
    with pytest.raises(ModuleNotFoundError):
        __import__("termin.visualization.render.framegraph.passes.ui_widget", fromlist=["UIWidgetPass"])

    with pytest.raises(ModuleNotFoundError):
        __import__("termin.visualization.ui.widgets.component", fromlist=["UIComponent"])


def test_dead_visualization_legacy_paths_are_removed() -> None:
    removed_modules = [
        "termin.visualization",
        "termin.visualization.core",
        "termin.visualization.core.scene",
        "termin.visualization.components",
        "termin.visualization.ui",
        "termin.visualization.render",
        "termin.visualization.render.shadow",
        "termin.visualization.render.shadow.shadow_camera",
        "termin.visualization.render.materials.pick_material",
        "termin.visualization.render.materials.simple",
        "termin.visualization.render.materials.grid_material",
        "termin.visualization.render.materials.unknown_material",
        "termin.visualization.render.materials.shadow_material",
        "termin.visualization.render.materials.depth_material",
        "termin.visualization.render.glsl_preprocessor",
        "termin.visualization.render.offscreen_context",
        "termin.visualization.render.texture",
        "termin.visualization.render.lighting",
        "termin.visualization.render.lighting.light_setup",
        "termin.visualization.render.lighting.shading",
        "termin.visualization.platform.backends",
        "termin.visualization.platform.backends.sdl_embedded",
        "termin.visualization.platform",
        "termin.visualization.platform.input_manager",
        "termin.visualization.core.world",
        "termin.visualization.core.viewport",
        "termin.visualization.core.viewport_config",
        "termin.visualization.core.render_target_config",
    ]

    for module_name in removed_modules:
        with pytest.raises(ModuleNotFoundError):
            __import__(module_name)


def test_removed_visualization_namespace_is_not_used_by_live_code() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    skipped_dirs = {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".venv",
        "build",
        "build-debug",
        "build-release",
        "docs",
        "sdk",
        "termin-thirdparty",
    }
    scanned_suffixes = {
        "",
        ".cmake",
        ".cpp",
        ".h",
        ".hpp",
        ".md",
        ".py",
        ".txt",
    }
    allowed_paths = {
        Path("termin-default-assets/tests/test_component_frame_pass_registries.py"),
    }

    offenders: list[str] = []
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(repo_root)
        if any(part in skipped_dirs for part in relative.parts):
            continue
        if relative in allowed_paths:
            continue
        if path.name != "CMakeLists.txt" and path.suffix not in scanned_suffixes:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if "termin.visualization" in content:
            offenders.append(str(relative))

    assert offenders == []
