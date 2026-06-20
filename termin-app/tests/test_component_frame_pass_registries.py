import sys
import types
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
    from termin.render_passes import UIWidgetPass
    from termin.ui_components import UIComponent

    assert UIWidgetPass.__module__ == "termin.render_passes.ui_widget"
    assert UIComponent.__module__ == "termin.ui_components.component"


def test_legacy_ui_component_and_pass_paths_are_removed() -> None:
    with pytest.raises(ModuleNotFoundError):
        __import__("termin.visualization.render.framegraph.passes.ui_widget", fromlist=["UIWidgetPass"])

    with pytest.raises(ModuleNotFoundError):
        __import__("termin.visualization.ui.widgets.component", fromlist=["UIComponent"])


def test_dead_visualization_legacy_paths_are_removed() -> None:
    removed_modules = [
        "termin.visualization.components",
        "termin.visualization.ui",
        "termin.visualization.render.shadow",
        "termin.visualization.render.shadow.shadow_camera",
        "termin.visualization.render.materials.pick_material",
        "termin.visualization.render.materials.simple",
        "termin.visualization.render.materials.grid_material",
        "termin.visualization.render.materials.unknown_material",
        "termin.visualization.render.materials.shadow_material",
        "termin.visualization.render.materials.depth_material",
        "termin.visualization.render.lighting",
        "termin.visualization.render.lighting.light_setup",
        "termin.visualization.render.lighting.shading",
        "termin.visualization.platform.backends",
        "termin.visualization.platform.backends.sdl_embedded",
        "termin.visualization.platform",
        "termin.visualization.platform.input_manager",
        "termin.visualization.core.world",
        "termin.visualization.core.viewport",
    ]

    for module_name in removed_modules:
        with pytest.raises(ModuleNotFoundError):
            __import__(module_name)
