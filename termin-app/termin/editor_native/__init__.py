"""Native UI host and production editor migration package."""

from .ui_host import (
    EditorWindowRegistry,
    EditorWindowSlot,
    NativeUiEventPolicy,
    NativeWidgetContent,
    resolve_native_ui_font,
)
from .shell import NativeEditorShell, build_native_editor_shell
from .profiler_panel import (
    NativeProfilerPanel,
    build_native_profiler_panel,
    connect_profiler_menu_toggle,
)
from .frame_profiler import (
    NativeFrameProfiler,
    build_native_frame_profiler,
    connect_frame_profiler_command,
)
from .registry_viewer import (
    NativeRegistryViewer,
    build_native_registry_catalog_viewer,
    build_native_registry_viewer,
    connect_registry_viewer_command,
)
from .project_browser import NativeProjectBrowser, build_native_project_browser
from .inspector_fields import NativeInspectorFields, build_native_inspector_fields
from .material_inspector import NativeMaterialInspector, build_native_material_inspector
from .entity_inspector import NativeEntityInspector, build_native_entity_inspector
from .scene_tree import NativeSceneTree, build_native_scene_tree
from .editor_viewport import NativeEditorViewport
from .display_workspace import NativeDisplayPage, NativeDisplayWorkspace
from .viewport_list import NativeViewportList, build_native_viewport_list
from .pipeline_editor import (
    NativePipelineEditor,
    build_native_pipeline_editor,
    connect_pipeline_editor_command,
)
from .framegraph_debugger import (
    NativeFramegraphDebugger,
    build_native_framegraph_debugger,
    connect_framegraph_debugger_command,
)
from .python_console import (
    NativePythonConsole,
    build_native_python_console,
    connect_python_console_command,
)
from .settings_dialog import (
    NativeSettingsDialog,
    build_native_settings_dialog,
    connect_settings_command,
)
from .about_dialog import NativeAboutDialog, build_native_about_dialog, connect_about_command
from .diagnostic_dialogs import (
    NativeAudioDebuggerDialog,
    NativeUndoHistoryDialog,
    build_native_audio_debugger_dialog,
    build_native_undo_history_dialog,
    connect_diagnostic_command,
)
from .scene_settings_dialogs import (
    NativeSceneNamesDialog,
    NativeScenePropertiesDialog,
    NativeShadowSettingsDialog,
    build_native_scene_names_dialog,
    build_native_scene_properties_dialog,
    build_native_shadow_settings_dialog,
    connect_scene_settings_command,
)
from .project_settings_dialog import (
    NativeProjectSettingsDialog,
    build_native_project_settings_dialog,
    connect_project_settings_command,
)
from .navigation_settings_dialogs import (
    NativeAgentTypesDialog,
    NativeNavMeshAreasDialog,
    build_native_agent_types_dialog,
    build_native_navmesh_areas_dialog,
    connect_navigation_settings_command,
)
from .spacemouse_settings_dialog import (
    NativeSpaceMouseSettingsDialog,
    build_native_spacemouse_settings_dialog,
    connect_spacemouse_settings_command,
)
from .scene_manager_dialog import (
    NativeSceneManagerDialog,
    build_native_scene_manager_dialog,
    connect_scene_manager_command,
)

__all__ = [
    "EditorWindowRegistry",
    "EditorWindowSlot",
    "NativeUiEventPolicy",
    "NativeWidgetContent",
    "NativeEditorShell",
    "NativeProfilerPanel",
    "NativeFrameProfiler",
    "NativeRegistryViewer",
    "NativeProjectBrowser",
    "NativeInspectorFields",
    "NativeMaterialInspector",
    "NativeEntityInspector",
    "NativeSceneTree",
    "NativeEditorViewport",
    "NativeDisplayPage",
    "NativeDisplayWorkspace",
    "NativeViewportList",
    "NativePipelineEditor",
    "NativeFramegraphDebugger",
    "NativePythonConsole",
    "NativeSettingsDialog",
    "NativeAboutDialog",
    "NativeAudioDebuggerDialog",
    "NativeUndoHistoryDialog",
    "NativeSceneNamesDialog",
    "NativeScenePropertiesDialog",
    "NativeShadowSettingsDialog",
    "NativeProjectSettingsDialog",
    "NativeAgentTypesDialog",
    "NativeNavMeshAreasDialog",
    "NativeSpaceMouseSettingsDialog",
    "NativeSceneManagerDialog",
    "build_native_editor_shell",
    "build_native_profiler_panel",
    "connect_profiler_menu_toggle",
    "build_native_frame_profiler",
    "connect_frame_profiler_command",
    "build_native_registry_viewer",
    "build_native_registry_catalog_viewer",
    "connect_registry_viewer_command",
    "build_native_project_browser",
    "build_native_inspector_fields",
    "build_native_material_inspector",
    "build_native_entity_inspector",
    "build_native_scene_tree",
    "build_native_viewport_list",
    "build_native_pipeline_editor",
    "connect_pipeline_editor_command",
    "build_native_framegraph_debugger",
    "connect_framegraph_debugger_command",
    "build_native_python_console",
    "connect_python_console_command",
    "build_native_settings_dialog",
    "connect_settings_command",
    "build_native_about_dialog",
    "connect_about_command",
    "build_native_audio_debugger_dialog",
    "build_native_undo_history_dialog",
    "connect_diagnostic_command",
    "build_native_scene_names_dialog",
    "build_native_scene_properties_dialog",
    "build_native_shadow_settings_dialog",
    "connect_scene_settings_command",
    "build_native_project_settings_dialog",
    "connect_project_settings_command",
    "build_native_agent_types_dialog",
    "build_native_navmesh_areas_dialog",
    "connect_navigation_settings_command",
    "build_native_spacemouse_settings_dialog",
    "connect_spacemouse_settings_command",
    "build_native_scene_manager_dialog",
    "connect_scene_manager_command",
    "resolve_native_ui_font",
]
