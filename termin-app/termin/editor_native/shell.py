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
from termin.editor_core.menu_bar_model import build_editor_menu_inventory
from termin.editor_native.metrics import EDITOR_UI_METRICS


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
    profiler_splitter: object
    navigation_tabs: object
    hierarchy_host: WidgetRef
    rendering_host: WidgetRef
    bottom_tabs: object
    project_host: WidgetRef
    console_host: WidgetRef
    python_console_host: WidgetRef
    workspace_host: WidgetRef
    inspector_host: WidgetRef
    profiler_host: WidgetRef
    debug_tabs: object
    menu_bar: object
    tool_bar: object
    prefab_tool_bar: object
    status_bar: object
    new_scene_command: int
    close_scene_command: int
    load_material_command: int
    load_components_command: int
    deploy_stdlib_command: int
    exit_command: int
    undo_command: int
    redo_command: int
    fullscreen_command: int
    camera_frustums_command: int
    load_scene_command: int
    save_scene_command: int
    save_scene_as_command: int
    game_menu_model: CommandModel
    edit_menu_model: CommandModel
    game_play_command: int
    toolbar_model: CommandModel
    toolbar_play_command: int
    toolbar_pause_command: int
    prefab_toolbar_model: CommandModel
    prefab_label_command: int
    prefab_save_command: int
    prefab_exit_command: int
    debug_menu_model: CommandModel
    profiler_command: int
    modules_command: int
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

    def set_profiler_docked(self, visible: bool) -> None:
        """Show the profiler as a horizontal peer of the editor workspace.

        The splitter is inserted only while the dock is visible.  Merely hiding
        a splitter child still reserves its extent in the native layout, which
        is why this explicit reparenting boundary belongs to the shell.
        """
        current = self.left_splitter.widget.children
        docked = any(
            child.handle == self.profiler_splitter.widget.handle for child in current
        )
        if docked == visible:
            self.profiler_host.visible = visible
            return
        if visible:
            self.right_splitter.widget.detach()
            self.profiler_splitter.set_first(self.right_splitter.widget)
            self.profiler_host.detach()
            self.profiler_splitter.set_second(self.profiler_host)
            self.profiler_splitter.widget.detach()
            self.left_splitter.set_second(self.profiler_splitter.widget)
        else:
            self.right_splitter.widget.detach()
            self.left_splitter.set_second(self.right_splitter.widget)
        self.profiler_host.visible = visible

    def set_prefab_editing(self, editing: bool, prefab_name: str | None = None) -> None:
        label = self.prefab_toolbar_model.command(self.prefab_label_command).data
        label.label = f"Editing Prefab: {prefab_name or ''}"
        self.prefab_toolbar_model.update(self.prefab_label_command, label)
        self.prefab_tool_bar.widget.visible = editing
        self.toolbar_model.set_enabled(self.toolbar_play_command, not editing)

    def menu_route(self, stable_id: str) -> NativeMenuActivationRoute:
        for index, entry in enumerate(self.menu_bar.entries):
            if entry.stable_id == stable_id:
                return NativeMenuActivationRoute(self.menu_bar, index)
        raise KeyError(f"native editor menu is not registered: {stable_id}")


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

    models: dict[str, CommandModel] = {}
    commands: dict[tuple[str, str], int] = {}
    entries = []
    for spec in build_editor_menu_inventory():
        items = list(spec.items)
        model = CommandModel()
        separator_index = 0
        for item in items:
            if item is None:
                separator_index += 1
                model.append(CommandData(f"separator-{separator_index}", kind=CommandKind.Separator))
                continue
            stable_id = item.label.lower().replace("...", "").replace("/", "-").replace(" ", "-")
            command_id = model.append(
                CommandData(
                    stable_id,
                    item.label,
                    shortcut=item.shortcut or "",
                    checkable=item.is_checkable,
                    checked=bool(item.state_getter()) if item.state_getter is not None else False,
                    enabled=item.label not in {"Undo", "Redo"},
                )
            )
            commands[(spec.name, item.label)] = command_id
        key = spec.name.lower()
        models[key] = model
        entries.append(MenuBarEntry(key, spec.name, model))

    file_menu = models["file"]
    edit_menu = models["edit"]
    view_menu = models["view"]
    scene_menu = models["scene"]
    navigation_menu = models["navigation"]
    game_menu = models["game"]
    debug_menu = models["debug"]
    help_menu = models["help"]
    new_scene_command = commands[("File", "New Scene")]
    close_scene_command = commands[("File", "Close Scene")]
    load_material_command = commands[("File", "Load Material...")]
    load_components_command = commands[("File", "Load Components...")]
    deploy_stdlib_command = commands[("File", "Deploy Standard Library...")]
    exit_command = commands[("File", "Exit")]
    load_scene_command = commands[("File", "Load Scene...")]
    save_scene_command = commands[("File", "Save Scene")]
    save_scene_as_command = commands[("File", "Save Scene As...")]
    settings_command = commands[("Edit", "Settings...")]
    undo_command = commands[("Edit", "Undo")]
    redo_command = commands[("Edit", "Redo")]
    project_settings_command = commands[("Edit", "Project Settings...")]
    spacemouse_settings_command = commands[("View", "SpaceMouse Settings...")]
    fullscreen_command = commands[("View", "Fullscreen")]
    scene_properties_command = commands[("Scene", "Scene Properties...")]
    scene_names_command = commands[("Scene", "Layers & Flags...")]
    shadow_settings_command = commands[("Scene", "Shadow Settings...")]
    pipeline_editor_command = commands[("Scene", "Pipeline Editor...")]
    agent_types_command = commands[("Navigation", "Agent Types...")]
    navmesh_areas_command = commands[("Navigation", "NavMesh Areas...")]
    game_play_command = commands[("Game", "Play")]
    build_project_command = commands[("Game", "Build Project...")]
    build_android_command = commands[("Game", "Build Android APK...")]
    build_quest_openxr_command = commands[("Game", "Quest/OpenXR Build...")]
    run_build_command = commands[("Game", "Run Build...")]
    run_standalone_command = commands[("Game", "Run Standalone...")]
    profiler_command = commands[("Debug", "Profiler")]
    modules_command = commands[("Debug", "Modules")]
    camera_frustums_command = commands[("Debug", "Camera Frustums")]
    scene_manager_command = commands[("Debug", "Scene Manager...")]
    framegraph_debugger_command = commands[("Debug", "Framegraph Texture Viewer...")]
    python_console_command = commands[("Debug", "Python Console...")]
    undo_history_command = commands[("Debug", "Undo/Redo Stack...")]
    audio_debugger_command = commands[("Debug", "Audio Debugger...")]
    inspect_registry_command = debug_menu.append(CommandData("inspect-registry", "Inspect Registry..."))
    core_registry_command = debug_menu.append(CommandData("core-registry", "Core Registry..."))
    resource_manager_command = debug_menu.append(CommandData("resource-manager", "Resource Manager..."))
    about_command = commands[("Help", "About Termin...")]
    menu_bar = document.create_menu_bar()
    menu_bar.entries = entries
    _append(document, root, menu_bar, Size(1280.0, 30.0), fixed_extent=30.0)

    toolbar_model = CommandModel()
    # Keep the caption self-contained. The native icon glyph is not guaranteed
    # by the editor font; reserving its absent glyph shifted "Play" right.
    toolbar_play_command = toolbar_model.append(CommandData("play", "Play"))
    toolbar_pause_command = toolbar_model.append(CommandData("pause", "Pause", enabled=False))
    tool_bar = document.create_tool_bar(toolbar_model)
    # The editor owns a single Play action in this strip. Center its visible
    # content while retaining the full-width toolbar background and hit area.
    tool_bar.centered = True
    prefab_toolbar_model = CommandModel()
    prefab_label_command = prefab_toolbar_model.append(
        CommandData("prefab-label", "Editing Prefab", enabled=False)
    )
    prefab_save_command = prefab_toolbar_model.append(CommandData("prefab-save", "Save"))
    prefab_exit_command = prefab_toolbar_model.append(CommandData("prefab-exit", "Exit"))
    prefab_tool_bar = document.create_tool_bar(prefab_toolbar_model)
    prefab_tool_bar.centered = True
    prefab_tool_bar.widget.visible = False

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
    workspace_host.add_fixed_child(tool_bar.widget, EDITOR_UI_METRICS.toolbar)
    workspace_host.add_fixed_child(
        prefab_tool_bar.widget,
        EDITOR_UI_METRICS.prefab_toolbar,
    )

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

    profiler_host = document.create_vstack("native-editor-profiler-host")
    profiler_host.stable_id = "editor.profiler-host"
    profiler_host.set_layout_spacing(0.0)
    profiler_host.preferred_size = Size(360.0, 406.0)
    profiler_host.visible = False
    debug_tabs = document.create_tab_view("native-editor-debug-tabs")
    debug_tabs.widget.stable_id = "editor.debug-tabs"
    profiler_host.add_stretch_child(debug_tabs.widget)

    profiler_splitter = document.create_splitter(True, "native-editor-profiler-splitter")
    profiler_splitter.widget.stable_id = "editor.profiler-splitter"
    profiler_splitter.set_split_fraction(0.78)
    profiler_splitter.set_min_extents(620.0, 280.0)

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

    python_console_host = document.create_vstack("native-editor-python-console-host")
    python_console_host.stable_id = "editor.python-console-host"
    python_console_host.set_layout_spacing(0.0)
    bottom_tabs.add_page("Python Console", python_console_host)

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
        profiler_splitter=profiler_splitter,
        navigation_tabs=navigation_tabs,
        hierarchy_host=hierarchy_host,
        rendering_host=rendering_host,
        bottom_tabs=bottom_tabs,
        project_host=project_host,
        console_host=console_host,
        python_console_host=python_console_host,
        workspace_host=workspace_host,
        inspector_host=inspector_host,
        profiler_host=profiler_host,
        debug_tabs=debug_tabs,
        menu_bar=menu_bar,
        tool_bar=tool_bar,
        prefab_tool_bar=prefab_tool_bar,
        status_bar=status_bar,
        new_scene_command=new_scene_command,
        close_scene_command=close_scene_command,
        load_material_command=load_material_command,
        load_components_command=load_components_command,
        deploy_stdlib_command=deploy_stdlib_command,
        exit_command=exit_command,
        undo_command=undo_command,
        redo_command=redo_command,
        fullscreen_command=fullscreen_command,
        camera_frustums_command=camera_frustums_command,
        load_scene_command=load_scene_command,
        save_scene_command=save_scene_command,
        save_scene_as_command=save_scene_as_command,
        game_menu_model=game_menu,
        edit_menu_model=edit_menu,
        game_play_command=game_play_command,
        toolbar_model=toolbar_model,
        toolbar_play_command=toolbar_play_command,
        toolbar_pause_command=toolbar_pause_command,
        prefab_toolbar_model=prefab_toolbar_model,
        prefab_label_command=prefab_label_command,
        prefab_save_command=prefab_save_command,
        prefab_exit_command=prefab_exit_command,
        debug_menu_model=debug_menu,
        profiler_command=profiler_command,
        modules_command=modules_command,
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
            navigation_menu,
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
