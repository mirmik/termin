"""Minimal production shell for vertical native editor migration slices."""

from __future__ import annotations

from dataclasses import dataclass

from termin.gui_native import (
    CommandData,
    CommandKind,
    CommandModel,
    Document,
    MenuBarEntry,
    Size,
    WidgetRef,
)


@dataclass(frozen=True)
class NativeEditorShell:
    root: WidgetRef
    central: WidgetRef
    project_host: WidgetRef
    workspace_host: WidgetRef
    inspector_host: WidgetRef
    menu_bar: object
    tool_bar: object
    status_bar: object
    debug_menu_model: CommandModel
    profiler_command: int
    inspect_registry_command: int
    core_registry_command: int
    resource_manager_command: int
    pipeline_editor_command: int
    framegraph_debugger_command: int
    python_console_command: int
    undo_history_command: int
    audio_debugger_command: int
    scene_properties_command: int
    scene_names_command: int
    shadow_settings_command: int
    agent_types_command: int
    navmesh_areas_command: int
    settings_command: int
    project_settings_command: int
    about_command: int
    command_models: tuple[CommandModel, ...]


def _append(
    document: Document,
    parent: WidgetRef,
    reference,
    preferred: Size,
    *,
    fixed_extent: float | None = None,
) -> WidgetRef:
    child = reference if isinstance(reference, WidgetRef) else document.ref(reference.handle)
    child.preferred_size = preferred
    if fixed_extent is not None:
        parent.add_fixed_child(child, fixed_extent)
    else:
        parent.add_stretch_child(child)
    return child


def build_native_editor_shell(document: Document) -> NativeEditorShell:
    root = document.create_vstack("native-editor-root")
    root.stable_id = "editor.root"
    if not document.add_root(root.handle):
        raise RuntimeError("failed to add native editor root")

    file_menu = CommandModel()
    file_menu.set_commands(
        [
            CommandData("new-scene", "New Scene", shortcut="Ctrl+N"),
            CommandData("open-project", "Open Project"),
            CommandData("separator", kind=CommandKind.Separator),
            CommandData("quit", "Quit", shortcut="Ctrl+Q"),
        ]
    )
    view_menu = CommandModel()
    view_menu.set_commands(
        [
            CommandData("scene-tree", "Scene Tree", checkable=True, checked=True),
            CommandData("inspector", "Inspector", checkable=True, checked=True),
        ]
    )
    edit_menu = CommandModel()
    settings_command = edit_menu.append(CommandData("settings", "Settings..."))
    project_settings_command = edit_menu.append(
        CommandData("project-settings", "Project Settings...")
    )
    scene_menu = CommandModel()
    scene_properties_command = scene_menu.append(
        CommandData("scene-properties", "Scene Properties...")
    )
    scene_names_command = scene_menu.append(CommandData("scene-names", "Layers & Flags..."))
    shadow_settings_command = scene_menu.append(
        CommandData("shadow-settings", "Shadow Settings...")
    )
    agent_types_command = scene_menu.append(CommandData("agent-types", "Agent Types..."))
    navmesh_areas_command = scene_menu.append(CommandData("navmesh-areas", "NavMesh Areas..."))
    debug_menu = CommandModel()
    profiler_command = debug_menu.append(CommandData("profiler", "Profiler", shortcut="F7", checkable=True))
    inspect_registry_command = debug_menu.append(CommandData("inspect-registry", "Inspect Registry...", shortcut="F8"))
    core_registry_command = debug_menu.append(CommandData("core-registry", "Core Registry...", shortcut="F9"))
    resource_manager_command = debug_menu.append(CommandData("resource-manager", "Resource Manager...", shortcut="F10"))
    pipeline_editor_command = debug_menu.append(
        CommandData("pipeline-editor", "Pipeline Editor...", shortcut="F11")
    )
    framegraph_debugger_command = debug_menu.append(
        CommandData("framegraph-debugger", "Framegraph Debugger...", shortcut="F12")
    )
    python_console_command = debug_menu.append(
        CommandData("python-console", "Python Console...", shortcut="F6")
    )
    undo_history_command = debug_menu.append(CommandData("undo-history", "Undo/Redo Stack..."))
    audio_debugger_command = debug_menu.append(CommandData("audio-debugger", "Audio Debugger..."))
    help_menu = CommandModel()
    about_command = help_menu.append(CommandData("about", "About Termin..."))
    menu_bar = document.create_menu_bar()
    menu_bar.entries = [
        MenuBarEntry("file", "File", file_menu),
        MenuBarEntry("edit", "Edit", edit_menu),
        MenuBarEntry("view", "View", view_menu),
        MenuBarEntry("scene", "Scene", scene_menu),
        MenuBarEntry("debug", "Debug", debug_menu),
        MenuBarEntry("help", "Help", help_menu),
    ]
    _append(document, root, menu_bar, Size(1280.0, 30.0), fixed_extent=30.0)

    toolbar_model = CommandModel()
    toolbar_model.set_commands(
        [
            CommandData("save", "Save", icon="S", shortcut="Ctrl+S"),
            CommandData("separator", kind=CommandKind.Separator),
            CommandData("play", "Play", icon="▶"),
        ]
    )
    tool_bar = document.create_tool_bar(toolbar_model)
    _append(document, root, tool_bar, Size(1280.0, 40.0), fixed_extent=40.0)

    central = document.create_hstack("native-editor-central")
    central.stable_id = "editor.central"
    _append(document, root, central, Size(1280.0, 626.0))
    project_host = document.create_vstack("native-editor-project-host")
    project_host.stable_id = "editor.project-host"
    project_host.set_layout_spacing(0.0)
    _append(document, central, project_host, Size(420.0, 626.0), fixed_extent=420.0)
    workspace_host = document.create_vstack("native-editor-workspace-host")
    workspace_host.stable_id = "editor.workspace-host"
    workspace_host.set_layout_spacing(0.0)
    _append(document, central, workspace_host, Size(500.0, 626.0))
    inspector_host = document.create_vstack("native-editor-inspector-host")
    inspector_host.stable_id = "editor.inspector-host"
    inspector_host.set_layout_spacing(0.0)
    _append(document, central, inspector_host, Size(360.0, 626.0), fixed_extent=360.0)

    status_bar = document.create_status_bar("Ready | Native editor host")
    _append(document, root, status_bar, Size(1280.0, 24.0), fixed_extent=24.0)
    return NativeEditorShell(
        root=root,
        central=central,
        project_host=project_host,
        workspace_host=workspace_host,
        inspector_host=inspector_host,
        menu_bar=menu_bar,
        tool_bar=tool_bar,
        status_bar=status_bar,
        debug_menu_model=debug_menu,
        profiler_command=profiler_command,
        inspect_registry_command=inspect_registry_command,
        core_registry_command=core_registry_command,
        resource_manager_command=resource_manager_command,
        pipeline_editor_command=pipeline_editor_command,
        framegraph_debugger_command=framegraph_debugger_command,
        python_console_command=python_console_command,
        undo_history_command=undo_history_command,
        audio_debugger_command=audio_debugger_command,
        scene_properties_command=scene_properties_command,
        scene_names_command=scene_names_command,
        shadow_settings_command=shadow_settings_command,
        agent_types_command=agent_types_command,
        navmesh_areas_command=navmesh_areas_command,
        settings_command=settings_command,
        project_settings_command=project_settings_command,
        about_command=about_command,
        command_models=(
            file_menu,
            edit_menu,
            view_menu,
            scene_menu,
            debug_menu,
            help_menu,
            toolbar_model,
        ),
    )


__all__ = ["NativeEditorShell", "build_native_editor_shell"]
