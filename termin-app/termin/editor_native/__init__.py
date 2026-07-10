"""Native UI host and production editor migration package."""

from .ui_host import NativeUiEventRouter, NativeUiHost, RouteResult, resolve_native_ui_font
from .shell import NativeEditorShell, build_native_editor_shell
from .profiler_panel import (
    NativeProfilerPanel,
    build_native_profiler_panel,
    connect_profiler_menu_toggle,
)
from .registry_viewer import (
    NativeRegistryViewer,
    build_native_registry_catalog_viewer,
    build_native_registry_viewer,
    connect_registry_viewer_command,
)
from .project_browser import NativeProjectBrowser, build_native_project_browser
from .inspector_fields import NativeInspectorFields, build_native_inspector_fields
from .entity_inspector import NativeEntityInspector, build_native_entity_inspector
from .scene_tree import NativeSceneTree, build_native_scene_tree
from .editor_viewport import NativeEditorViewport

__all__ = [
    "NativeUiEventRouter",
    "NativeUiHost",
    "NativeEditorShell",
    "NativeProfilerPanel",
    "NativeRegistryViewer",
    "NativeProjectBrowser",
    "NativeInspectorFields",
    "NativeEntityInspector",
    "NativeSceneTree",
    "NativeEditorViewport",
    "RouteResult",
    "build_native_editor_shell",
    "build_native_profiler_panel",
    "connect_profiler_menu_toggle",
    "build_native_registry_viewer",
    "build_native_registry_catalog_viewer",
    "connect_registry_viewer_command",
    "build_native_project_browser",
    "build_native_inspector_fields",
    "build_native_entity_inspector",
    "build_native_scene_tree",
    "resolve_native_ui_font",
]
