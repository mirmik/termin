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


class NativeMenuActivationRoute:
    """Expose activations from exactly one MenuBar entry."""

    def __init__(self, menu_bar, menu_index: int) -> None:
        self._menu_bar = menu_bar
        self._menu_index = menu_index

    def connect_activated(self, callback):
        def routed(menu_index: int, command_id: int, command) -> None:
            if menu_index == self._menu_index:
                callback(menu_index, command_id, command)

        return self._menu_bar.connect_activated(routed)


@dataclass(frozen=True)
class NativeEditorShell:
    root: WidgetRef
    central: WidgetRef
    main_splitter: object
    left_splitter: object
    right_splitter: object
    navigation_tabs: object
    hierarchy_host: WidgetRef
    rendering_host: WidgetRef
    bottom_tabs: object
    project_host: WidgetRef
    console_host: WidgetRef
    workspace_host: WidgetRef
    inspector_host: WidgetRef
    menu_bar: object
    tool_bar: object
    status_bar: object
    new_scene_command: int
    load_scene_command: int
    save_scene_command: int
    save_scene_as_command: int
    game_menu_model: CommandModel
    game_play_command: int
    toolbar_model: CommandModel
    toolbar_play_command: int
    debug_menu_model: CommandModel
    profiler_command: int
    inspect_registry_command: int
    core_registry_command: int
    resource_manager_command: int
    scene_manager_command: int
    pipeline_editor_command: int
    framegraph_debugger_command: int
    python_console_command: int
    undo_history_command: int
    audio_debugger_command: int
    spacemouse_settings_command: int
    scene_properties_command: int
    scene_names_command: int
    shadow_settings_command: int
    agent_types_command: int
    navmesh_areas_command: int
    settings_command: int
    project_settings_command: int
    build_project_command: int
    build_android_command: int
    build_quest_openxr_command: int
    run_build_command: int
    run_standalone_command: int
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
    new_scene_command = file_menu.append(
        CommandData("new-scene", "New Scene", shortcut="Ctrl+N")
    )
    load_scene_command = file_menu.append(
        CommandData("load-scene", "Load Scene...", shortcut="Ctrl+O")
    )
    save_scene_command = file_menu.append(
        CommandData("save-scene", "Save Scene", shortcut="Ctrl+S")
    )
    save_scene_as_command = file_menu.append(
        CommandData("save-scene-as", "Save Scene As...", shortcut="Ctrl+Shift+S")
    )
    file_menu.append(CommandData("open-project", "Open Project"))
    file_menu.append(CommandData("separator", kind=CommandKind.Separator))
    file_menu.append(CommandData("quit", "Quit", shortcut="Ctrl+Q"))
    view_menu = CommandModel()
    view_menu.set_commands(
        [
            CommandData("scene-tree", "Scene Tree", checkable=True, checked=True),
            CommandData("inspector", "Inspector", checkable=True, checked=True),
        ]
    )
    spacemouse_settings_command = view_menu.append(
        CommandData("spacemouse-settings", "SpaceMouse Settings...")
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
    game_menu = CommandModel()
    game_play_command = game_menu.append(CommandData("play", "Play", shortcut="F5"))
    build_project_command = game_menu.append(CommandData("build-project", "Build Project..."))
    build_android_command = game_menu.append(
        CommandData("build-android", "Build Android APK...")
    )
    build_quest_openxr_command = game_menu.append(
        CommandData("build-quest-openxr", "Quest/OpenXR Build...")
    )
    run_build_command = game_menu.append(CommandData("run-build", "Run Build..."))
    run_standalone_command = game_menu.append(
        CommandData("run-standalone", "Run Standalone...")
    )
    debug_menu = CommandModel()
    profiler_command = debug_menu.append(CommandData("profiler", "Profiler", shortcut="F7", checkable=True))
    inspect_registry_command = debug_menu.append(CommandData("inspect-registry", "Inspect Registry...", shortcut="F8"))
    core_registry_command = debug_menu.append(CommandData("core-registry", "Core Registry...", shortcut="F9"))
    resource_manager_command = debug_menu.append(CommandData("resource-manager", "Resource Manager...", shortcut="F10"))
    scene_manager_command = debug_menu.append(CommandData("scene-manager", "Scene Manager..."))
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
        MenuBarEntry("game", "Game", game_menu),
        MenuBarEntry("debug", "Debug", debug_menu),
        MenuBarEntry("help", "Help", help_menu),
    ]
    _append(document, root, menu_bar, Size(1280.0, 30.0), fixed_extent=30.0)

    toolbar_model = CommandModel()
    toolbar_play_command = toolbar_model.append(CommandData("play", "Play", icon="▶"))
    tool_bar = document.create_tool_bar(toolbar_model)

    central = document.create_vstack("native-editor-central")
    central.stable_id = "editor.central"
    _append(document, root, central, Size(1280.0, 626.0))

    navigation_tabs = document.create_tab_view("native-editor-navigation-tabs")
    navigation_tabs.widget.stable_id = "editor.navigation-tabs"
    navigation_tabs.widget.preferred_size = Size(280.0, 406.0)

    hierarchy_host = document.create_vstack("native-editor-hierarchy-host")
    hierarchy_host.stable_id = "editor.hierarchy-host"
    hierarchy_host.set_layout_spacing(0.0)
    navigation_tabs.add_page("Scene", hierarchy_host)

    rendering_host = document.create_vstack("native-editor-rendering-host")
    rendering_host.stable_id = "editor.rendering-host"
    rendering_host.set_layout_spacing(0.0)
    navigation_tabs.add_page("Rendering", rendering_host)

    workspace_host = document.create_vstack("native-editor-workspace-host")
    workspace_host.stable_id = "editor.workspace-host"
    workspace_host.set_layout_spacing(0.0)
    workspace_host.preferred_size = Size(640.0, 406.0)
    workspace_host.add_fixed_child(tool_bar.widget, 40.0)

    inspector_host = document.create_vstack("native-editor-inspector-host")
    inspector_host.stable_id = "editor.inspector-host"
    inspector_host.set_layout_spacing(0.0)
    inspector_host.preferred_size = Size(360.0, 406.0)

    right_splitter = document.create_splitter(True, "native-editor-right-splitter")
    right_splitter.widget.stable_id = "editor.right-splitter"
    right_splitter.set_first(workspace_host)
    right_splitter.set_second(inspector_host)
    # Match the legacy editor's initial 1476:346 workspace/inspector split
    # at the 2048 px reference window while retaining responsive fractions.
    right_splitter.set_split_fraction(0.81)
    right_splitter.set_min_extents(360.0, 260.0)

    left_splitter = document.create_splitter(True, "native-editor-left-splitter")
    left_splitter.widget.stable_id = "editor.left-splitter"
    left_splitter.set_first(navigation_tabs.widget)
    left_splitter.set_second(right_splitter.widget)
    # The legacy hierarchy column starts at roughly 225 px in a 2048 px window.
    left_splitter.set_split_fraction(0.11)
    left_splitter.set_min_extents(180.0, 620.0)

    bottom_tabs = document.create_tab_view("native-editor-bottom-tabs")
    bottom_tabs.widget.stable_id = "editor.bottom-tabs"
    bottom_tabs.widget.preferred_size = Size(1280.0, 220.0)

    project_host = document.create_vstack("native-editor-project-host")
    project_host.stable_id = "editor.project-host"
    project_host.set_layout_spacing(0.0)
    bottom_tabs.add_page("Project", project_host)

    console_host = document.create_vstack("native-editor-console-host")
    console_host.stable_id = "editor.console-host"
    console_host.set_layout_spacing(0.0)
    bottom_tabs.add_page("Console", console_host)

    main_splitter = document.create_splitter(False, "native-editor-main-splitter")
    main_splitter.widget.stable_id = "editor.main-splitter"
    main_splitter.set_first(left_splitter.widget)
    main_splitter.set_second(bottom_tabs.widget)
    # The legacy bottom panel occupies about 27% of the editor content height.
    main_splitter.set_split_fraction(0.72)
    main_splitter.set_min_extents(240.0, 120.0)
    central.add_stretch_child(main_splitter.widget)

    status_bar = document.create_status_bar("Ready | Native editor host")
    _append(document, root, status_bar, Size(1280.0, 24.0), fixed_extent=24.0)
    return NativeEditorShell(
        root=root,
        central=central,
        main_splitter=main_splitter,
        left_splitter=left_splitter,
        right_splitter=right_splitter,
        navigation_tabs=navigation_tabs,
        hierarchy_host=hierarchy_host,
        rendering_host=rendering_host,
        bottom_tabs=bottom_tabs,
        project_host=project_host,
        console_host=console_host,
        workspace_host=workspace_host,
        inspector_host=inspector_host,
        menu_bar=menu_bar,
        tool_bar=tool_bar,
        status_bar=status_bar,
        new_scene_command=new_scene_command,
        load_scene_command=load_scene_command,
        save_scene_command=save_scene_command,
        save_scene_as_command=save_scene_as_command,
        game_menu_model=game_menu,
        game_play_command=game_play_command,
        toolbar_model=toolbar_model,
        toolbar_play_command=toolbar_play_command,
        debug_menu_model=debug_menu,
        profiler_command=profiler_command,
        inspect_registry_command=inspect_registry_command,
        core_registry_command=core_registry_command,
        resource_manager_command=resource_manager_command,
        scene_manager_command=scene_manager_command,
        pipeline_editor_command=pipeline_editor_command,
        framegraph_debugger_command=framegraph_debugger_command,
        python_console_command=python_console_command,
        undo_history_command=undo_history_command,
        audio_debugger_command=audio_debugger_command,
        spacemouse_settings_command=spacemouse_settings_command,
        scene_properties_command=scene_properties_command,
        scene_names_command=scene_names_command,
        shadow_settings_command=shadow_settings_command,
        agent_types_command=agent_types_command,
        navmesh_areas_command=navmesh_areas_command,
        settings_command=settings_command,
        project_settings_command=project_settings_command,
        build_project_command=build_project_command,
        build_android_command=build_android_command,
        build_quest_openxr_command=build_quest_openxr_command,
        run_build_command=run_build_command,
        run_standalone_command=run_standalone_command,
        about_command=about_command,
        command_models=(
            file_menu,
            edit_menu,
            view_menu,
            scene_menu,
            game_menu,
            debug_menu,
            help_menu,
            toolbar_model,
        ),
    )


__all__ = [
    "NativeEditorShell",
    "NativeMenuActivationRoute",
    "build_native_editor_shell",
]
