"""Native editor root entrypoint used during production migration."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from tgfx import Tgfx2Context
from termin.display import PresentationMode, WindowManager, WindowedGraphicsSession, quit_sdl
from termin.editor_core.component_editor_extension import (
    ComponentEditorExtensionSession,
    ComponentExtensionPresentation,
)
from termin.editor_core.application_icon import apply_editor_window_icon
from termin.editor_core.entity_inspector_model import EntityInspectorController
from termin.editor_core.inspector_model import InspectorKind, InspectorModel
from termin.editor_core.inspector_resources import InspectorResourceCatalog
from termin.editor_core.material_inspector_model import MaterialInspectorController
from termin.editor_core.modules_panel_model import ModulesPanelController
from termin.editor_core.rendering_inspector_models import (
    DisplayInspectorController,
    RenderTargetInspectorController,
    ViewportInspectorController,
)
from termin.editor_core.pipeline_editor_model import PipelineEditorController
from termin.editor_core.pipeline_inspector_model import PipelineInspectorController
from termin.editor_core.framegraph_debugger_service import EditorFramegraphDebuggerService
from termin.editor_core.python_console_model import PythonConsoleController
from termin.editor_core.scene_edit_service import EditorSceneEditService
from termin.editor_core.settings_model import EditorSettingsController
from termin.editor_core.about_model import build_editor_about_info
from termin.editor_core.profiler_model import ProfilerController
from termin.editor_core.profiler_capture import (
    ProfilerCaptureCoordinator,
)
from termin.editor_core.project_browser_model import ProjectBrowserController
from termin.editor_core.project_file_action_controller import ProjectFileActionController
from termin.editor_core.project_operations import ProjectOperations
from termin.editor_core.external_editor import reveal_in_file_manager
from termin.editor_core.prefab_edit_controller import PrefabEditController
from termin.editor_core.registry_sources import (
    build_core_registry_pages,
    build_resource_manager_pages,
)
from termin.editor_core.registry_viewer_model import (
    InspectRegistrySource,
    RegistryCatalogController,
    RegistryCollectionController,
)
from termin.editor_core.scene_hierarchy_model import SceneHierarchyController
from termin.editor_core.scene_structure_observer import SceneStructureObserver
from termin.editor_core.undo_stack import UndoStack
from termin.editor_core.undo_history_model import UndoHistoryController
from termin.editor_core.audio_debugger_model import create_audio_debugger_controller
from termin.editor_core.scene_settings_model import (
    SceneNamesController,
    ScenePropertiesController,
    ShadowSettingsController,
)
from termin.editor_core.project_settings_model import ProjectSettingsController
from termin.editor_core.project_build_controller import ProjectBuildController
from termin.editor_native.project_session_controller import NativeProjectSessionController
from termin.editor_core.scene_file_controller import SceneFileController
from termin.editor_core.editor_state_io import EditorStateIO
from termin.editor_core.shader_runtime import resolve_slangc, resolve_termin_shaderc
from termin.editor_core.game_mode_model import GameModeModel
from termin.editor_core.game_mode_session_connectors import (
    EditorGameModeConnector,
    RenderGameModeConnector,
)
from termin.editor_core.primary_render_scene_binding import PrimaryRenderSceneBinding
from termin.editor_core.navigation_settings_model import NavigationSettingsController
from termin.editor_core.spacemouse_controller import SpaceMouseController
from termin.editor_core.spacemouse_settings_model import SpaceMouseSettingsController
from termin.editor_core.scene_manager_model import SceneManagerController
from termin.editor_core.editor_scene_session import EditorSceneSession
from termin.editor_core.editor_log_model import EditorLogModel
from termin.editor_core.editor_session_presentation import EditorSessionPresentationModel
from termin.editor_core.render_scene_session import RenderSceneSession
from termin.editor_core.rendering_factories import (
    PipelineAssetResolver,
    RenderingFactoryRegistration,
)
from termin.editor_core.viewport_list_model import ViewportListController
from termin.editor_native.component_extensions import (
    NativeComponentExtensionContext,
    NativeComponentExtensionProjectorRegistry,
    register_native_component_extensions,
)
from termin.editor_native.dialog_service import NativeDialogService
from termin.editor_native.display_workspace import NativeDisplayWorkspace
from termin.editor_native.editor_viewport import NativeEditorViewport
from termin.editor_native.game_mode_controller import NativeGameModeController
from termin.editor_native.editor_log import build_native_editor_log
from termin.editor_native.editor_session import EditorSession
from termin.editor_native.event_loop import attach_native_editor_event_loop
from termin.editor_native.quest_openxr_build_dialog import (
    build_native_quest_openxr_build_dialog,
)
from termin.editor_native.entity_inspector import build_native_entity_inspector
from termin.editor_native.material_inspector import build_native_material_inspector
from termin.editor_native.modules_panel import build_native_modules_panel
from termin.editor_native.resource_inspectors import build_native_resource_inspectors
from termin.editor_native.rendering_inspectors import build_native_rendering_inspectors
from termin.editor_native.profiler_panel import (
    build_native_profiler_panel,
    connect_profiler_menu_toggle,
)
from termin.editor_native.frame_profiler import (
    build_native_frame_profiler,
    connect_frame_profiler_command,
)
from termin.editor_native.pipeline_editor import (
    build_native_pipeline_editor,
    connect_pipeline_editor_command,
)
from termin.editor_native.pipeline_inspector import build_native_pipeline_inspector
from termin.editor_native.tool_inspector import build_native_tool_inspector
from termin.editor_native.framegraph_debugger import (
    build_native_framegraph_debugger,
    connect_framegraph_debugger_command,
)
from termin.editor_native.python_console import (
    build_native_python_console,
    connect_python_console_command,
)
from termin.editor_native.settings_dialog import (
    build_native_settings_dialog,
    connect_settings_command,
)
from termin.editor_native.about_dialog import build_native_about_dialog, connect_about_command
from termin.editor_native.diagnostic_dialogs import (
    build_native_audio_debugger_dialog,
    build_native_undo_history_dialog,
    connect_diagnostic_command,
)
from termin.editor_native.scene_settings_dialogs import (
    build_native_scene_names_dialog,
    build_native_scene_properties_dialog,
    build_native_shadow_settings_dialog,
    connect_scene_settings_command,
)
from termin.editor_native.project_settings_dialog import (
    build_native_project_settings_dialog,
    connect_project_settings_command,
)
from termin.editor_native.navigation_settings_dialogs import (
    build_native_agent_types_dialog,
    build_native_navmesh_areas_dialog,
    connect_navigation_settings_command,
)
from termin.editor_native.spacemouse_settings_dialog import (
    build_native_spacemouse_settings_dialog,
    connect_spacemouse_settings_command,
)
from termin.editor_native.scene_manager_dialog import (
    build_native_scene_manager_dialog,
    connect_scene_manager_command,
)
from termin.editor_native.project_browser import build_native_project_browser
from termin.editor_native.project_extensions import NativeProjectEditorContext
from termin.editor_native.registry_viewer import (
    build_native_registry_catalog_viewer,
    build_native_registry_viewer,
    connect_registry_viewer_command,
)
from termin.editor_native.scene_tree import build_native_scene_tree
from termin.editor_native.shell import build_native_editor_shell
from termin.editor_native.ui_host import EditorWindowRegistry, NativeWidgetContent
from termin.editor_native.viewport_list import build_native_viewport_list
from termin.gui_native import Rect, WidgetRef


_logger = logging.getLogger(__name__)


def _complete_editor_scene_render(native_viewport, host) -> None:
    """Finish viewport work and schedule presentation of the produced image."""
    native_viewport.after_render()
    host.request_render_update()


def _clear_component_extension_viewport(extension_context) -> None:
    extension_context.on_viewport_tool_state_changed = None
    extension_context.viewport_geometry = None


def _close_game_mode_controller(game_mode_controller) -> None:
    if game_mode_controller.model.is_game_mode:
        game_mode_controller.model.toggle_game_mode()
    game_mode_controller.close()


def _compose_native_editor(
    session: EditorSession,
    engine,
    debug_resource: str | None = None,
    no_scene: bool = False,
) -> None:
    """Build one native document as dependency-ordered owned stages."""

    runtime_stage = session.begin_stage("runtime bootstrap")
    from termin.bootstrap import bootstrap_editor
    from termin.editor_core.resource_manager import configure_editor_resource_manager_factory
    from termin.editor_core.mcp_server import start_editor_mcp_server
    from termin.editor_core.python_executor import EditorPythonExecutor
    from termin.engine import create_scene, scene as engine_scene

    bootstrap_editor()
    configure_editor_resource_manager_factory()
    from termin.editor_core.resource_manager import ResourceManager

    resource_manager = runtime_stage.own("resource manager", ResourceManager.instance())
    from termin.editor_core.resource_loader import register_editor_builtin_resources

    register_editor_builtin_resources(resource_manager)
    from termin.editor_core.shader_runtime import configure_sdk_shader_runtime

    render_engine = engine.rendering_manager.render_engine
    configure_sdk_shader_runtime("native-editor", render_engine=render_engine)
    settings_controller = runtime_stage.own(
        "settings controller",
        EditorSettingsController(),
    )
    settings_snapshot = settings_controller.load()
    engine.target_fps = settings_snapshot.fps_limit
    presentation_mode = (
        PresentationMode.VSYNC
        if settings_snapshot.vsync_enabled
        else PresentationMode.IMMEDIATE
    )
    platform_stage = session.begin_stage(
        "native platform",
        after_engine_shutdown=True,
    )
    platform_stage.add_cleanup("SDL runtime", quit_sdl)
    graphics_session = platform_stage.own(
        "windowed graphics session",
        WindowedGraphicsSession.create_native(),
        cleanup=lambda: graphics_session.close(),
    )
    render_engine.set_graphics_host(graphics_session.graphics)
    render_engine.ensure_tgfx2()
    graphics = platform_stage.own(
        "graphics context",
        Tgfx2Context.from_runtime(graphics_session.graphics),
    )
    native_windows = platform_stage.own(
        "framework-neutral window manager",
        WindowManager(graphics_session),
        cleanup=lambda: native_windows.close(),
    )
    main_window_handle = native_windows.create_window(
        "Termin Editor — Native UI",
        1280,
        720,
        presentation_mode,
    )
    host = platform_stage.own(
        "native widget content",
        NativeWidgetContent(
            native_windows,
            main_window_handle,
            graphics=graphics,
        ),
    )
    window = host.window
    apply_editor_window_icon(window)
    window.maximize()
    window_manager = platform_stage.own(
        "editor window registry",
        EditorWindowRegistry(native_windows, main_window_handle, host),
        cleanup=lambda: window_manager.close(),
    )
    shell = platform_stage.own(
        "native editor shell",
        build_native_editor_shell(host.document),
    )
    host.event_policy.shortcut_dispatcher = shell.menu_bar.dispatch_shortcut
    file_menu = shell.menu_route("file")
    edit_menu = shell.menu_route("edit")
    view_menu = shell.menu_route("view")
    scene_menu = shell.menu_route("scene")
    navigation_menu = shell.menu_route("navigation")
    game_menu = shell.menu_route("game")
    debug_menu = shell.menu_route("debug")
    help_menu = shell.menu_route("help")

    def request_editor_render() -> None:
        engine.scene_manager.request_render()
        host.request_render_update()

    def refresh_editor_ui() -> None:
        """Present UI mutations made by a synchronous long-running operation."""
        request_editor_render()
        host.render()

    diagnostics_stage = session.begin_stage("diagnostics UI")
    session_presentation = diagnostics_stage.own(
        "session presentation",
        EditorSessionPresentationModel(),
    )

    def apply_session_presentation(snapshot) -> None:
        shell.status_bar.text = snapshot.status_text
        window.set_title(snapshot.window_title)
        host.request_render_update()

    session_presentation.changed.connect(apply_session_presentation)
    apply_session_presentation(session_presentation.snapshot)
    editor_log_model = EditorLogModel()
    editor_log = diagnostics_stage.own(
        "editor log",
        build_native_editor_log(
            host.document,
            editor_log_model,
            request_editor_render,
        ),
        cleanup=lambda: editor_log.close(),
    )
    shell.console_host.add_stretch_child(editor_log.root)

    def set_profile_ui(enabled: bool) -> None:
        engine.profile_ui = enabled

    profiler_capture_coordinator = ProfilerCaptureCoordinator()
    capture_profiler = profiler_capture_coordinator.profiler
    profiler_controller = ProfilerController(
        profiler_capture_coordinator.profiler,
        get_include_ui=lambda: bool(engine.profile_ui),
        set_include_ui=set_profile_ui,
        capture_coordinator=profiler_capture_coordinator,
    )
    profiler_panel = build_native_profiler_panel(host.document, profiler_controller)
    shell.debug_tabs.add_page("Profiler", profiler_panel.root)
    from termin.editor._editor_native import FrameProfilerController

    frame_profiler_controller = FrameProfilerController(engine, capacity=3600)
    frame_profiler = diagnostics_stage.own(
        "frame profiler",
        build_native_frame_profiler(
            window_manager,
            frame_profiler_controller,
        ),
        cleanup=lambda: frame_profiler.close(),
    )
    connect_frame_profiler_command(
        debug_menu,
        shell.frame_profiler_command,
        frame_profiler,
    )

    from termin.project_modules.runtime import get_project_modules_runtime

    modules_controller = ModulesPanelController(
        get_project_modules_runtime(engine.scene_manager),
        progress_callback=refresh_editor_ui,
    )
    modules_panel = diagnostics_stage.own(
        "modules panel",
        build_native_modules_panel(host.document, modules_controller),
        cleanup=lambda: modules_panel.close(),
    )
    shell.debug_tabs.add_page("Modules", modules_panel.root)
    debug_visibility = {"Profiler": False, "Modules": False}

    def set_debug_panel_visible(name: str, visible: bool) -> None:
        debug_visibility[name] = visible
        if visible:
            shell.debug_tabs.selected_index = 0 if name == "Profiler" else 1
        shell.set_profiler_docked(any(debug_visibility.values()))
        request_editor_render()

    connect_profiler_menu_toggle(
        debug_menu,
        shell.profiler_command,
        profiler_panel,
        request_editor_render,
        lambda visible: set_debug_panel_visible("Profiler", visible),
    )

    def on_modules_menu(_index: int, command_id: int, command) -> None:
        if command_id != shell.modules_command:
            return
        if command.checked:
            modules_panel.refresh()
        set_debug_panel_visible("Modules", command.checked)

    debug_menu.connect_activated(on_modules_menu)
    diagnostics_stage.own("editor log model", editor_log_model)
    diagnostics_stage.own("profiler capture coordinator", profiler_capture_coordinator)
    diagnostics_stage.own("profiler controller", profiler_controller)
    diagnostics_stage.own("profiler panel", profiler_panel)
    diagnostics_stage.own("frame profiler controller", frame_profiler_controller)
    diagnostics_stage.own("modules controller", modules_controller)

    workspace_stage = session.begin_stage("scene workspace")
    from termin.display import set_clipboard_text
    from termin.inspect import InspectRegistry

    registry_controller = RegistryCollectionController(
        InspectRegistrySource(InspectRegistry.instance()),
        copy_text=set_clipboard_text,
    )

    def editor_viewport() -> Rect:
        width, height = window.framebuffer_size()
        return Rect(0.0, 0.0, float(width), float(height))

    initial_scene = None if no_scene else create_scene(name="default")
    active_scene = [initial_scene]

    def current_scene():
        return active_scene[0]

    editor_scene_name = "untitled"
    if initial_scene is not None:
        engine.scene_manager.register_scene(
            editor_scene_name,
            initial_scene.scene_handle(),
        )
        workspace_stage.add_cleanup(
            "initial editor scene registration",
            lambda: engine.scene_manager.unregister_scene(editor_scene_name),
        )
        engine.scene_manager.set_mode(editor_scene_name, engine_scene.SceneMode.STOP)
    undo_stack = UndoStack()
    dialog_service = NativeDialogService(
        host.document,
        viewport=editor_viewport,
        request_render=request_editor_render,
        register_color_picker=host.register_color_picker,
        unregister_color_picker=host.unregister_color_picker,
    )
    undo_history_controller = UndoHistoryController(undo_stack)

    def update_undo_commands() -> None:
        shell.edit_menu_model.set_enabled(shell.undo_command, undo_stack.can_undo)
        shell.edit_menu_model.set_enabled(shell.redo_command, undo_stack.can_redo)

    def push_undo_command(command, merge: bool = False) -> None:
        undo_stack.push(command, merge=merge)
        undo_history_controller.refresh()
        update_undo_commands()

    scene_properties_dialog = None
    scene_names_dialog = None
    shadow_settings_dialog = None
    scene_properties_controller = None
    scene_names_controller = None
    shadow_settings_controller = None
    if initial_scene is not None:
        scene_properties_controller = ScenePropertiesController(
            initial_scene,
            push_undo_command=push_undo_command,
            on_changed=request_editor_render,
        )
        scene_properties_dialog = build_native_scene_properties_dialog(
            host.document,
            scene_properties_controller,
            dialog_service=dialog_service,
            viewport=editor_viewport,
            request_render=request_editor_render,
        )
        workspace_stage.own(
            "scene properties dialog",
            scene_properties_dialog,
            cleanup=lambda: scene_properties_dialog.close(),
        )
        scene_names_controller = SceneNamesController(initial_scene)
        scene_names_dialog = build_native_scene_names_dialog(
            host.document,
            scene_names_controller,
            viewport=editor_viewport,
            request_render=request_editor_render,
        )
        workspace_stage.own(
            "scene names dialog",
            scene_names_dialog,
            cleanup=lambda: scene_names_dialog.close(),
        )
        shadow_settings_controller = ShadowSettingsController(initial_scene, on_changed=request_editor_render)
        shadow_settings_dialog = build_native_shadow_settings_dialog(
            host.document,
            shadow_settings_controller,
            viewport=editor_viewport,
            request_render=request_editor_render,
        )
        workspace_stage.own(
            "shadow settings dialog",
            shadow_settings_dialog,
            cleanup=lambda: shadow_settings_dialog.close(),
        )
        for command_id, scene_dialog in (
            (shell.scene_properties_command, scene_properties_dialog),
            (shell.scene_names_command, scene_names_dialog),
            (shell.shadow_settings_command, shadow_settings_dialog),
        ):
            connect_scene_settings_command(scene_menu, command_id, scene_dialog)

    undo_history_dialog = workspace_stage.own(
        "undo history dialog",
        build_native_undo_history_dialog(
            host.document,
            undo_history_controller,
            viewport=editor_viewport,
            request_render=request_editor_render,
        ),
        cleanup=lambda: undo_history_dialog.close(),
    )
    connect_diagnostic_command(
        debug_menu,
        shell.undo_history_command,
        undo_history_dialog,
    )
    audio_debugger_controller = create_audio_debugger_controller()
    audio_debugger_dialog = workspace_stage.own(
        "audio debugger dialog",
        build_native_audio_debugger_dialog(
            host.document,
            audio_debugger_controller,
            viewport=editor_viewport,
            request_render=request_editor_render,
        ),
        cleanup=lambda: audio_debugger_dialog.close(),
    )
    connect_diagnostic_command(
        debug_menu,
        shell.audio_debugger_command,
        audio_debugger_dialog,
    )
    host.apply_font_size(settings_snapshot.font_size)

    def apply_render_only_active_display(enabled: bool) -> None:
        if display_workspace is not None:
            display_workspace.set_render_only_active_display(enabled)

    settings_dialog = workspace_stage.own(
        "settings dialog",
        build_native_settings_dialog(
            host.document,
            settings_controller,
            dialog_service=dialog_service,
            viewport=editor_viewport,
            request_render=request_editor_render,
            apply_font_size=host.apply_font_size,
            apply_render_only_active_display=apply_render_only_active_display,
        ),
        cleanup=lambda: settings_dialog.close(),
    )
    connect_settings_command(
        edit_menu,
        shell.settings_command,
        settings_dialog,
    )
    about_dialog = workspace_stage.own(
        "about dialog",
        build_native_about_dialog(
            host.document,
            build_editor_about_info(backend_name=window.backend),
            viewport=editor_viewport,
            request_render=request_editor_render,
        ),
        cleanup=lambda: about_dialog.close(),
    )
    connect_about_command(help_menu, shell.about_command, about_dialog)
    selected_entity = None
    display_workspace: NativeDisplayWorkspace | None = None
    native_viewport: NativeEditorViewport | None = None
    inspector_host = None
    suppress_scene_inspector = False
    inspector_model = InspectorModel(resource_manager)
    inspector_model.set_scene(initial_scene)
    pipeline_editor_controller = PipelineEditorController()
    inspector_resource_catalog = InspectorResourceCatalog(resource_manager)
    entity_inspector_controller = EntityInspectorController(undo_handler=push_undo_command)
    entity_inspector_controller.set_scene(initial_scene)
    entity_inspector = build_native_entity_inspector(
        host.document,
        entity_inspector_controller,
        request_render=request_editor_render,
        viewport=editor_viewport,
        show_color_dialog=dialog_service.show_color,
        show_layer_mask_dialog=dialog_service.show_layer_mask,
        show_texture_preview=host.register_image_preview,
        show_input=dialog_service.show_input,
        resource_catalog=inspector_resource_catalog,
    )
    workspace_stage.add_cleanup(
        "entity inspector snapshot handler",
        lambda: entity_inspector_controller.set_snapshot_changed_handler(None),
    )
    material_inspector = build_native_material_inspector(
        host.document,
        MaterialInspectorController(resource_manager, changed=request_editor_render),
        request_render=request_editor_render,
        resource_catalog=inspector_resource_catalog,
        show_color_dialog=dialog_service.show_color,
        show_texture_preview=host.register_image_preview,
    )
    texture_inspector, mesh_inspector, glb_inspector = build_native_resource_inspectors(
        host.document,
        resource_manager=resource_manager,
        request_render=request_editor_render,
        changed=request_editor_render,
        show_texture_preview=host.register_image_preview,
    )

    def open_inspected_pipeline() -> None:
        pipeline_editor.refresh()
        pipeline_editor.show()

    pipeline_inspector = build_native_pipeline_inspector(
        host.document,
        PipelineInspectorController(
            pipeline_editor_controller,
            open_editor=open_inspected_pipeline,
        ),
        request_render=request_editor_render,
    )
    tool_inspector = build_native_tool_inspector(host.document)
    extension_projectors = NativeComponentExtensionProjectorRegistry(host.document)
    register_native_component_extensions(extension_projectors)
    extension_context = NativeComponentExtensionContext(
        engine=engine,
        document=host.document,
        request_render=request_editor_render,
        resource_manager=resource_manager,
    )

    def present_component_extension(
        _type_name: str,
        presentation: ComponentExtensionPresentation,
    ) -> None:
        if presentation.left_panel is not None:
            _logger.error("Native component extensions do not yet expose a left panel host")
            raise ValueError("native component extension left panel is unsupported")
        right_panel = presentation.right_panel
        if right_panel is not None and not isinstance(right_panel, WidgetRef):
            _logger.error("Native component extension projector returned a non-native right panel")
            raise TypeError("native component extension right panel must be WidgetRef")
        entity_inspector.set_extension_panel(right_panel)

    extension_session = ComponentEditorExtensionSession(
        editor=lambda: extension_context,
        presenter=extension_projectors.project,
        present=present_component_extension,
        clear_presentation=entity_inspector.clear_extension_panel,
    )
    workspace_stage.own(
        "component extension session",
        extension_session,
        cleanup=lambda: extension_session.clear(),
    )

    def on_component_selected(entity: object | None, component_ref: object | None) -> None:
        if entity is None or component_ref is None:
            extension_session.clear()
            return
        extension_session.select_component(entity, component_ref, component_ref.type_name)

    entity_inspector_controller.set_component_selection_changed_handler(on_component_selected)
    workspace_stage.add_cleanup(
        "component selection handler",
        lambda: entity_inspector_controller.set_component_selection_changed_handler(None),
    )

    def on_scene_object_selected(obj: object | None) -> None:
        nonlocal selected_entity, suppress_scene_inspector
        selected_entity = obj
        if suppress_scene_inspector:
            suppress_scene_inspector = False
        else:
            inspector_model.resync_from_selection(obj)
        if native_viewport is not None:
            native_viewport.select_scene_object(
                obj,
                active_tools=extension_context.active_viewport_tools,
            )
        request_editor_render()

    scene_hierarchy_controller = SceneHierarchyController(
        initial_scene,
        undo_handler=push_undo_command,
        dialog_service=dialog_service,
        on_object_selected=on_scene_object_selected,
        request_viewport_update=request_editor_render,
    )
    scene_structure_observer = SceneStructureObserver(
        scene_hierarchy_controller.rebuild,
        request_editor_render,
    )
    workspace_stage.own(
        "scene structure observer",
        scene_structure_observer,
        cleanup=lambda: scene_structure_observer.close(),
    )
    scene_structure_observer.set_scene(initial_scene)
    scene_tree = build_native_scene_tree(
        host.document,
        scene_hierarchy_controller,
        viewport=editor_viewport,
        request_render=request_editor_render,
    )
    workspace_stage.add_cleanup(
        "scene hierarchy snapshot handler",
        lambda: scene_hierarchy_controller.set_snapshot_changed_handler(None),
    )
    shell.hierarchy_host.add_stretch_child(scene_tree.root)

    def drop_project_file(path: str, x: float, y: float, modifiers: int = 0) -> bool:
        if scene_tree.drop_file(path, x, y, modifiers):
            return True
        if native_viewport is None:
            return False
        bounds = native_viewport.root.bounds
        if not (bounds.x <= x < bounds.x + bounds.width and bounds.y <= y < bounds.y + bounds.height):
            return False
        return native_viewport.geometry.drop_project_file(
            path,
            Path(path).suffix.casefold(),
            x,
            y,
        )

    host.event_policy.file_drop_handler = drop_project_file

    viewport_list_controller = ViewportListController()
    viewport_list = build_native_viewport_list(
        host.document,
        viewport_list_controller,
        viewport=editor_viewport,
        request_render=request_editor_render,
        show_input=dialog_service.show_input,
    )
    shell.rendering_host.add_stretch_child(viewport_list.root)

    def sync_viewport_list() -> None:
        displays = [] if display_workspace is None else list(display_workspace.displays)
        display_handles = {display.handle for display in displays}
        for display in engine.rendering_manager.displays:
            if display.handle not in display_handles:
                displays.append(display)
                display_handles.add(display.handle)
        viewport_list_controller.set_displays(displays)
        viewport_list_controller.set_render_targets(engine.rendering_manager.managed_render_targets)

    def on_viewport_list_entity_selected(entity) -> None:
        nonlocal suppress_scene_inspector
        suppress_scene_inspector = entity is None
        scene_tree.select_object(entity)

    def on_viewport_list_display_selected(display) -> None:
        if display is not None and display_workspace is not None:
            display_workspace.select_display(display)
        if display is not None and inspector_host is not None:
            inspector_host.show_display(display, display.name or "Display")
        session_presentation.update(
            message="Display: none" if display is None else f"Display: {display.name or 'unnamed'}"
        )
        request_editor_render()

    def on_viewport_list_viewport_selected(viewport) -> None:
        if viewport is not None and inspector_host is not None:
            inspector_host.show_viewport(viewport)
        session_presentation.update(
            message="Viewport: none" if viewport is None else f"Viewport: {viewport.name or 'unnamed'}"
        )
        request_editor_render()

    def on_viewport_list_target_selected(target) -> None:
        if target is not None and inspector_host is not None:
            inspector_host.show_render_target(target)
        session_presentation.update(
            message="Render target: none" if target is None else f"Render target: {target.name or 'unnamed'}"
        )
        request_editor_render()

    def add_viewport(display) -> None:
        scene = current_scene()
        if scene is None or native_viewport is None or display_workspace is None:
            dialog_service.show_error("Add Viewport", "No scene is attached.")
            return
        viewport = display.create_viewport(
            scene=scene,
            camera=native_viewport.camera,
            rect=(0.0, 0.0, 1.0, 1.0),
        )
        if not engine.rendering_manager.register_viewport_attachment(display, viewport):
            display.remove_viewport(viewport)
            dialog_service.show_error("Add Viewport", "Failed to register viewport attachment.")
            return
        try:
            display_workspace.configure_viewport_input(display, viewport)
        except Exception:
            _logger.exception("Native workspace failed to configure viewport input")
            engine.rendering_manager.unregister_viewport_attachment(viewport)
            display.remove_viewport(viewport)
            dialog_service.show_error("Add Viewport", "Failed to configure viewport input.")
            return
        sync_viewport_list()
        request_editor_render()

    def remove_viewport(viewport) -> None:
        editor_owned = None if native_viewport is None else native_viewport.attachment.viewport
        if editor_owned is not None and viewport._viewport_handle() == editor_owned._viewport_handle():
            dialog_service.show_error(
                "Remove Viewport",
                "The production editor viewport is owned by the editor host and cannot be removed.",
            )
            return
        display = engine.rendering_manager.get_display_for_viewport(viewport)
        if display is None:
            _logger.error("Native viewport list cannot find owner display for removal")
            return
        if display_workspace is not None:
            display_workspace.release_viewport_input(display, viewport)
        engine.rendering_manager.unregister_viewport_attachment(viewport)
        display.remove_viewport(viewport)
        sync_viewport_list()
        request_editor_render()

    def add_display() -> None:
        if display_workspace is None:
            _logger.error("Native viewport list requested a display before workspace creation")
            return
        display = display_workspace.create_display()
        # Unlike scene restoration, this is an explicit user request. Make the
        # new display immediately visible; the workspace selection callback
        # keeps the rendering tree and inspector in sync.
        display_workspace.select_display(display)
        sync_viewport_list()
        request_editor_render()

    def remove_display(display) -> None:
        if display_workspace is None:
            _logger.error("Native viewport list requested display removal without a workspace")
            return
        if display_workspace.is_editor_display(display):
            dialog_service.show_error(
                "Remove Display",
                "The editor display is owned by the native workspace and cannot be removed.",
            )
            return
        if display_workspace.remove_display(display):
            sync_viewport_list()
            request_editor_render()

    def add_render_target(kind: str) -> None:
        from termin.render_framework._render_framework_native import render_target_new

        name = "XRStereoTarget" if kind == "xr_stereo" else "RenderTarget"
        target = render_target_new(name)
        target.kind = kind
        scene = current_scene()
        if scene is not None:
            target.scene = scene
        engine.rendering_manager.register_managed_render_target(target)
        sync_viewport_list()
        request_editor_render()

    def remove_render_target(target) -> None:
        from termin.editor_core.rendering_model import RenderingModel

        RenderingModel(engine.rendering_manager).remove_render_target(
            target,
            scene=current_scene(),
        )
        sync_viewport_list()
        request_editor_render()

    viewport_list_controller.entity_selected.connect(on_viewport_list_entity_selected)
    viewport_list_controller.display_selected.connect(on_viewport_list_display_selected)
    viewport_list_controller.viewport_selected.connect(on_viewport_list_viewport_selected)
    viewport_list_controller.render_target_selected.connect(on_viewport_list_target_selected)
    viewport_list_controller.display_add_requested.connect(add_display)
    viewport_list_controller.display_remove_requested.connect(remove_display)
    viewport_list_controller.viewport_add_requested.connect(add_viewport)
    viewport_list_controller.viewport_remove_requested.connect(remove_viewport)
    viewport_list_controller.render_target_add_requested.connect(add_render_target)
    viewport_list_controller.render_target_remove_requested.connect(remove_render_target)
    viewport_list_controller.viewport_renamed.connect(lambda _viewport, _name: request_editor_render())
    viewport_list_controller.render_target_renamed.connect(lambda _target, _name: request_editor_render())

    if initial_scene is not None:
        display_workspace = workspace_stage.own(
            "display workspace",
            NativeDisplayWorkspace.create(
                host.document,
                shell.workspace_host,
                device=host.device,
                rendering_manager=engine.rendering_manager,
                scene=initial_scene,
                request_render=request_editor_render,
                render_only_active_display=settings_snapshot.render_only_active_display,
            ),
            cleanup=lambda: display_workspace.close(),
        )
        native_viewport = display_workspace.editor_viewport
        native_viewport.geometry.set_scene_tree_controller_getter(lambda: scene_hierarchy_controller)
        display_workspace.on_display_selected = lambda display: viewport_list_controller.select(
            viewport_list_controller.display_stable_id(display)
        )

        def on_viewport_selection_changed(entity: object) -> None:
            scene_tree.select_object(entity if entity.valid() else None)
            request_editor_render()

        def on_viewport_hover_changed(_entity: object) -> None:
            request_editor_render()

        def on_viewport_transform_end(old_pose: object, new_pose: object) -> None:
            from termin.editor_core.editor_commands import TransformEditCommand

            transform_gizmo = native_viewport.interaction.transform_gizmo
            if transform_gizmo is None or not transform_gizmo.target.valid():
                return
            push_undo_command(
                TransformEditCommand(
                    transform=transform_gizmo.target.transform,
                    old_pose=old_pose,
                    new_pose=new_pose,
                ),
                merge=False,
            )
            inspector_model.resync_from_selection(transform_gizmo.target)
            request_editor_render()

        native_viewport.configure_interaction(
            on_selection_changed=on_viewport_selection_changed,
            on_hover_changed=on_viewport_hover_changed,
            on_entity_click=extension_context.dispatch_viewport_click,
            on_pointer=extension_context.dispatch_viewport_pointer,
            on_key=extension_context.dispatch_viewport_key,
            on_transform_end=on_viewport_transform_end,
            draw_overlays=extension_context.draw_viewport_overlays,
        )
        extension_context.on_viewport_tool_state_changed = native_viewport.sync_gizmo_target
        extension_context.viewport_geometry = native_viewport.geometry
        workspace_stage.add_cleanup(
            "component extension viewport binding",
            lambda: _clear_component_extension_viewport(extension_context),
        )
        workspace_stage.add_cleanup(
            "scene after-render callback",
            lambda: engine.scene_manager.set_on_after_render(None),
        )
        engine.scene_manager.set_on_after_render(lambda: _complete_editor_scene_render(native_viewport, host))
        sync_viewport_list()

    def inspector_scenes() -> tuple[object, ...]:
        return tuple(
            scene
            for name in engine.scene_manager.scene_names()
            if (scene := engine.scene_manager.get_scene(name)) is not None
        )

    def inspector_displays(viewport) -> tuple[object, ...]:
        displays = viewport_list_controller.displays
        if display_workspace is None or not display_workspace.can_move_viewport(viewport):
            return displays
        return tuple(display for display in displays if not display_workspace.is_editor_display(display))

    def move_inspected_viewport(viewport, source, target) -> None:
        if display_workspace is None:
            raise RuntimeError("native display workspace is unavailable")
        display_workspace.move_viewport(viewport, source, target)

    def rendering_inspector_changed() -> None:
        if display_workspace is not None:
            for display in display_workspace.displays:
                display_workspace.set_display_title(display, display.name or "Display")
        sync_viewport_list()
        request_editor_render()

    display_inspector_controller = DisplayInspectorController(
        changed=rendering_inspector_changed,
    )
    viewport_inspector_controller = ViewportInspectorController(
        displays=inspector_displays,
        scenes=inspector_scenes,
        render_targets=lambda: engine.rendering_manager.managed_render_targets,
        owner_display=engine.rendering_manager.get_display_for_viewport,
        move_viewport=move_inspected_viewport,
        can_move_viewport=lambda viewport: (
            display_workspace is not None and display_workspace.can_move_viewport(viewport)
        ),
        changed=rendering_inspector_changed,
    )
    render_target_inspector_controller = RenderTargetInspectorController(
        resource_manager,
        scenes=inspector_scenes,
        layer_names=lambda: entity_inspector_controller.snapshot.layer_names,
        create_default_pipeline=lambda: engine.rendering_manager.create_pipeline("Default"),
        changed=rendering_inspector_changed,
    )
    inspector_host = build_native_rendering_inspectors(
        host.document,
        model=inspector_model,
        entity_inspector=entity_inspector,
        material_inspector=material_inspector,
        texture_inspector=texture_inspector,
        mesh_inspector=mesh_inspector,
        glb_inspector=glb_inspector,
        pipeline_inspector=pipeline_inspector,
        tool_inspector=tool_inspector,
        display_controller=display_inspector_controller,
        viewport_controller=viewport_inspector_controller,
        render_target_controller=render_target_inspector_controller,
        request_render=request_editor_render,
        show_color_dialog=dialog_service.show_color,
        show_layer_mask_dialog=dialog_service.show_layer_mask,
    )
    shell.inspector_host.add_stretch_child(inspector_host.root)

    def refresh_live_display_inspector(_context) -> None:
        if inspector_model.kind is not InspectorKind.DISPLAY:
            return
        previous = display_inspector_controller.snapshot
        current = display_inspector_controller.refresh()
        if current != previous:
            inspector_host.display_inspector.rebuild(current)

    host.add_pre_render_callback(refresh_live_display_inspector)
    workspace_stage.add_cleanup(
        "live display inspector callback",
        lambda: host.remove_pre_render_callback(refresh_live_display_inspector),
    )

    from termin.editor_core.rendering_model import RenderingModel

    rendering_model = RenderingModel(engine.rendering_manager)
    rendering_factory_registration = None
    pipeline_reload_binding = None
    if display_workspace is not None:
        from termin.default_assets.render.pipeline_reload_binding import PipelineReloadBinding

        pipeline_resolver = PipelineAssetResolver(resource_manager)
        rendering_factory_registration = RenderingFactoryRegistration(
            engine.rendering_manager,
            display_factory=display_workspace.create_display,
            pipeline_factory=pipeline_resolver.resolve,
        )
        rendering_factory_registration.install()
        workspace_stage.own(
            "rendering factory registration",
            rendering_factory_registration,
            cleanup=lambda: rendering_factory_registration.close(),
        )
        pipeline_reload_binding = PipelineReloadBinding(
            resource_manager,
            engine.rendering_manager,
        )
        workspace_stage.own(
            "pipeline reload binding",
            pipeline_reload_binding,
            cleanup=lambda: pipeline_reload_binding.close(),
        )

    render_scene_session = None
    if display_workspace is not None:
        render_scene_session = RenderSceneSession(
            engine.scene_manager,
            rendering_model,
            display_workspace,
            sync_viewports=sync_viewport_list,
            request_render=request_editor_render,
        )

    spacemouse = workspace_stage.own(
        "SpaceMouse controller",
        SpaceMouseController(),
        cleanup=lambda: spacemouse.close(),
    )
    if native_viewport is not None:
        spacemouse.open(native_viewport.attachment, request_editor_render)
    spacemouse_settings_dialog = workspace_stage.own(
        "SpaceMouse settings dialog",
        build_native_spacemouse_settings_dialog(
            host.document,
            SpaceMouseSettingsController(spacemouse, on_changed=request_editor_render),
            viewport=editor_viewport,
            request_render=request_editor_render,
        ),
        cleanup=lambda: spacemouse_settings_dialog.close(),
    )
    connect_spacemouse_settings_command(
        view_menu,
        shell.spacemouse_settings_command,
        spacemouse_settings_dialog,
    )
    editor_scene_session = None
    if (
        native_viewport is not None
        and scene_properties_controller is not None
        and scene_names_controller is not None
        and shadow_settings_controller is not None
    ):

        def dismiss_scene_dialogs() -> None:
            for scene_dialog in (
                scene_properties_dialog,
                scene_names_dialog,
                shadow_settings_dialog,
            ):
                if scene_dialog is not None and scene_dialog.dialog.open:
                    scene_dialog.dialog.close()

        def clear_scene_selection() -> None:
            nonlocal selected_entity
            selected_entity = None
            extension_session.clear()
            inspector_model.clear()
            native_viewport.select_scene_object(None)

        def scene_switched(scene) -> None:
            active_scene[0] = scene
            scene_structure_observer.set_scene(scene)
            session_presentation.update(
                scene_label="No Scene" if scene is None else (active_scene_name() or "Untitled")
            )
            inspector_model.set_scene(scene)
            if scene is not None:
                native_viewport.rebind_input_manager()
            sync_viewport_list()
            request_editor_render()

        editor_scene_session = EditorSceneSession(
            native_viewport.attachment,
            scene_hierarchy=scene_hierarchy_controller,
            entity_inspector=entity_inspector_controller,
            scene_properties=scene_properties_controller,
            scene_names=scene_names_controller,
            shadow_settings=shadow_settings_controller,
            clear_selection=clear_scene_selection,
            before_switch=dismiss_scene_dialogs,
            on_switched=scene_switched,
        )

    def attach_editor_scene(name: str, *, restore_state: bool = True, **_options):
        if editor_scene_session is None:
            raise RuntimeError("native editor scene attachment is unavailable")
        scene = engine.scene_manager.get_scene(name)
        if scene is None:
            raise ValueError(f"scene '{name}' does not exist")
        return editor_scene_session.attach(scene, restore_state=restore_state)

    def detach_editor_scene(*, save_state: bool = True, **_options):
        if editor_scene_session is None:
            raise RuntimeError("native editor scene attachment is unavailable")
        return editor_scene_session.detach(save_state=save_state)

    scene_manager_dialog = workspace_stage.own(
        "scene manager dialog",
        build_native_scene_manager_dialog(
            host.document,
            SceneManagerController(
                engine.scene_manager,
                get_editor_attachment=lambda: None if native_viewport is None else native_viewport.attachment,
                on_editor_attach=attach_editor_scene if editor_scene_session is not None else None,
                on_editor_detach=detach_editor_scene if editor_scene_session is not None else None,
                on_render_attach=None if render_scene_session is None else render_scene_session.attach,
                on_render_detach=None if render_scene_session is None else render_scene_session.detach,
                on_changed=request_editor_render,
            ),
            dialog_service=dialog_service,
            viewport=editor_viewport,
            request_render=request_editor_render,
        ),
        cleanup=lambda: scene_manager_dialog.close(),
    )
    connect_scene_manager_command(
        debug_menu,
        shell.scene_manager_command,
        scene_manager_dialog,
    )

    workspace_stage.own("inspect registry controller", registry_controller)
    if initial_scene is not None:
        workspace_stage.own("initial scene", initial_scene)
    workspace_stage.own("undo stack", undo_stack)
    workspace_stage.own("dialog service", dialog_service)
    workspace_stage.own("undo history controller", undo_history_controller)
    workspace_stage.own("audio debugger controller", audio_debugger_controller)
    workspace_stage.own("inspector model", inspector_model)
    workspace_stage.own("pipeline editor controller", pipeline_editor_controller)
    workspace_stage.own("inspector resource catalog", inspector_resource_catalog)
    workspace_stage.own("entity inspector controller", entity_inspector_controller)
    workspace_stage.own("entity inspector", entity_inspector)
    workspace_stage.own("material inspector", material_inspector)
    workspace_stage.own("pipeline inspector", pipeline_inspector)
    workspace_stage.own("tool inspector", tool_inspector)
    workspace_stage.own("component extension projectors", extension_projectors)
    workspace_stage.own("component extension context", extension_context)
    workspace_stage.own("scene hierarchy controller", scene_hierarchy_controller)
    workspace_stage.own("scene tree", scene_tree)
    workspace_stage.own("viewport list controller", viewport_list_controller)
    workspace_stage.own("viewport list", viewport_list)
    workspace_stage.own("rendering model", rendering_model)
    if render_scene_session is not None:
        workspace_stage.own("render scene session", render_scene_session)
    if editor_scene_session is not None:
        workspace_stage.own("editor scene session", editor_scene_session)
    workspace_stage.own("rendering inspector host", inspector_host)

    project_stage = session.begin_stage("project tools")
    registry_viewer = project_stage.own(
        "inspect registry viewer",
        build_native_registry_viewer(
            host.document,
            registry_controller,
            viewport=editor_viewport,
            request_render=request_editor_render,
        ),
    )
    connect_registry_viewer_command(
        debug_menu,
        shell.inspect_registry_command,
        registry_viewer,
    )

    core_registry_controller = RegistryCatalogController(
        build_core_registry_pages(),
        copy_text=set_clipboard_text,
    )
    core_registry_viewer = project_stage.own(
        "core registry viewer",
        build_native_registry_catalog_viewer(
            host.document,
            core_registry_controller,
            title="Core Registry",
            viewport=editor_viewport,
            request_render=request_editor_render,
        ),
    )
    connect_registry_viewer_command(
        debug_menu,
        shell.core_registry_command,
        core_registry_viewer,
    )

    prefab_open_handler: list[Callable[[str], None] | None] = [None]

    def open_prefab_from_project(path: str) -> None:
        handler = prefab_open_handler[0]
        if handler is None:
            _logger.error("Native prefab edit session is not initialized")
            return
        handler(path)

    project_file_actions = ProjectFileActionController(
        load_scene_from_file=lambda path: scene_file_controller.load_scene_from_file(path),
        open_prefab=open_prefab_from_project,
        get_inspector_model=lambda: inspector_model,
    )

    def on_project_file_selected(path: Path) -> None:
        project_file_actions.select_file(path)

    def on_project_file_activated(path: Path) -> None:
        project_file_actions.activate_file(path)

    project_browser_controller = ProjectBrowserController(
        on_file_selected=on_project_file_selected,
        on_file_activated=on_project_file_activated,
        copy_text=set_clipboard_text,
        reveal_path=lambda path: reveal_in_file_manager(path),
        operations=ProjectOperations(dialog_service),
    )
    project_browser = project_stage.own(
        "project browser",
        build_native_project_browser(
            host.document,
            project_browser_controller,
            viewport=editor_viewport,
            request_render=request_editor_render,
            file_drop_handler=drop_project_file,
        ),
    )
    shell.project_host.add_stretch_child(project_browser.root)

    from termin.editor_core.settings import EditorSettings
    from termin.launcher.recent import read_launch_project

    project_file = read_launch_project()
    if project_file is None:
        last_project = EditorSettings.instance().get_last_project_file()
        project_file = str(last_project) if last_project is not None else None
    if project_file is not None:
        project_path = Path(project_file)
        if not project_path.is_file() or project_path.suffix != ".terminproj":
            _logger.error("Native editor ignored invalid startup project: %s", project_file)
            project_file = None

    def active_scene_name() -> str | None:
        scene = current_scene()
        if scene is None:
            return None
        handle = scene.scene_handle()
        for name in engine.scene_manager.scene_names():
            candidate = engine.scene_manager.get_scene(name)
            if candidate is None:
                continue
            candidate_handle = candidate.scene_handle()
            if candidate_handle.index == handle.index and candidate_handle.generation == handle.generation:
                return name
        _logger.error("Native editor active scene is not registered in SceneManager")
        return None

    def log_build_message(message: str) -> None:
        _logger.info("Project build: %s", message)
        editor_log_model.append(message)
        session_presentation.update(message=message)

    def update_window_title() -> None:
        scene_name = active_scene_name()
        session_presentation.update(scene_label=scene_name or "No Scene")

    pre_prefab_scene_name: str | None = None

    def on_prefab_mode_changed(editing: bool, prefab_name: str | None) -> None:
        nonlocal pre_prefab_scene_name
        shell.set_prefab_editing(editing, prefab_name)
        if game_mode_controller is not None:
            game_mode_controller.set_available(not editing)
        if editing:
            prefab_scene = engine.scene_manager.get_scene("prefab")
            if prefab_scene is None or editor_scene_session is None:
                raise RuntimeError("prefab edit scene attachment is unavailable")
            if pre_prefab_scene_name and render_scene_session is not None:
                render_scene_session.detach(pre_prefab_scene_name, save_state=True)
            editor_scene_session.attach(prefab_scene, restore_state=False)
            if render_scene_session is not None:
                render_scene_session.attach("prefab")
            session_presentation.update(scene_label=f"Prefab: {prefab_name or ''}")
        else:
            previous = pre_prefab_scene_name
            pre_prefab_scene_name = None
            if previous and engine.scene_manager.has_scene(previous):
                attach_editor_scene(previous, restore_state=True)
                if render_scene_session is not None:
                    render_scene_session.attach(previous)
            update_window_title()
        request_editor_render()

    prefab_edit_controller = PrefabEditController(
        engine.scene_manager,
        resource_manager,
        on_mode_changed=on_prefab_mode_changed,
        on_request_update=request_editor_render,
        log_message=log_build_message,
        get_editor_scene_name=active_scene_name,
    )

    def open_prefab(path: str) -> None:
        nonlocal pre_prefab_scene_name
        if prefab_edit_controller.is_editing:
            _logger.error(
                "Native editor is already editing prefab '%s'",
                prefab_edit_controller.prefab_name,
            )
            return
        pre_prefab_scene_name = active_scene_name()
        if not prefab_edit_controller.open_prefab(path):
            pre_prefab_scene_name = None

    prefab_open_handler[0] = open_prefab

    def save_prefab() -> None:
        if not prefab_edit_controller.save():
            _logger.error("Native editor failed to save active prefab")

    def exit_prefab() -> None:
        if not prefab_edit_controller.is_editing:
            return
        if editor_scene_session is not None and active_scene_name() == "prefab":
            editor_scene_session.detach(save_state=False)
        if render_scene_session is not None and engine.scene_manager.has_scene("prefab"):
            render_scene_session.detach("prefab", save_state=False)
        prefab_edit_controller.exit()

    def on_prefab_toolbar(_index: int, command_id: int, _command) -> None:
        if command_id == shell.prefab_save_command:
            save_prefab()
        elif command_id == shell.prefab_exit_command:
            exit_prefab()

    shell.prefab_tool_bar.connect_activated(on_prefab_toolbar)

    editor_state_io = None
    if native_viewport is not None:
        editor_state_io = EditorStateIO(
            native_viewport.attachment,
            native_viewport.interaction,
        )
        editor_state_io.get_scene = current_scene
        editor_state_io.on_entity_selected = scene_tree.select_object
        editor_state_io.get_expanded_entity_uuids = scene_hierarchy_controller.get_expanded_entity_uuids
        editor_state_io.set_expanded_entity_uuids = scene_hierarchy_controller.set_expanded_entity_uuids

    scene_file_controller = SceneFileController(
        scene_manager=engine.scene_manager,
        get_dialog_service=lambda: dialog_service,
        get_editor_scene_name=active_scene_name,
        set_editor_scene_name=lambda _name: None,
        get_scene=current_scene,
        get_project_path=lambda: (
            None if project_browser_controller.root_path is None else str(project_browser_controller.root_path)
        ),
        get_editor_state_io=lambda: editor_state_io,
        prepare_scene_for_save=lambda name: (
            True if render_scene_session is None else render_scene_session.sync_scene_render_state(name)
        ),
        has_editor_attachment=lambda: editor_scene_session is not None,
        detach_editor_from_scene=detach_editor_scene,
        detach_scene_from_render=lambda name, **_options: (
            False if render_scene_session is None else render_scene_session.detach(name)
        ),
        attach_editor_to_scene=attach_editor_scene,
        attach_scene_to_render=lambda name: (
            False if render_scene_session is None else render_scene_session.attach(name)
        ),
        get_scene_tree_controller=lambda: scene_hierarchy_controller,
        get_inspector_controller=lambda: entity_inspector_controller,
        observe_scene_events=scene_structure_observer.set_scene,
        on_rendering_changed=sync_viewport_list,
        request_viewport_update=request_editor_render,
        update_window_title=update_window_title,
        log_to_console=log_build_message,
    )

    scene_file_commands = {
        shell.new_scene_command: scene_file_controller.new_scene,
        shell.load_scene_command: scene_file_controller.load_scene,
        shell.save_scene_command: scene_file_controller.save_scene,
        shell.save_scene_as_command: scene_file_controller.save_scene_as,
    }

    def on_scene_file_command(_menu_index: int, command_id: int, _command) -> None:
        callback = scene_file_commands.get(command_id)
        if callback is not None:
            callback()

    file_menu.connect_activated(on_scene_file_command)

    quest_openxr_build_dialog = project_stage.own(
        "Quest OpenXR build dialog",
        build_native_quest_openxr_build_dialog(
            host.document,
            viewport=editor_viewport,
            request_render=request_editor_render,
        ),
        cleanup=lambda: quest_openxr_build_dialog.close(),
    )

    def show_quest_openxr_build(entry) -> None:
        quest_openxr_build_dialog.show_entry(entry, on_log=log_build_message)

    project_build_controller = ProjectBuildController(
        scene_manager=engine.scene_manager,
        get_current_project_path=lambda: (
            None if project_browser_controller.root_path is None else str(project_browser_controller.root_path)
        ),
        get_editor_scene_name=active_scene_name,
        save_scene=scene_file_controller.save_scene,
        log_to_console=log_build_message,
        show_quest_openxr=show_quest_openxr_build,
    )

    project_build_commands = {
        shell.build_project_command: project_build_controller.build_project,
        shell.build_android_command: project_build_controller.build_android,
        shell.build_quest_openxr_command: project_build_controller.show_quest_openxr_build_dialog,
        shell.run_build_command: project_build_controller.run_build,
        shell.run_standalone_command: project_build_controller.run_standalone,
    }

    def on_project_build_command(_menu_index: int, command_id: int, _command) -> None:
        callback = project_build_commands.get(command_id)
        if callback is not None:
            callback()

    game_menu.connect_activated(on_project_build_command)

    pipeline_directory = project_browser_controller.root_path or Path.cwd()
    pipeline_editor = project_stage.own(
        "pipeline editor",
        build_native_pipeline_editor(
            host.document,
            pipeline_editor_controller,
            dialog_service=dialog_service,
            viewport=editor_viewport,
            request_render=request_editor_render,
            default_directory=pipeline_directory,
        ),
        cleanup=lambda: pipeline_editor.close(),
    )
    connect_pipeline_editor_command(
        scene_menu,
        shell.pipeline_editor_command,
        pipeline_editor,
    )

    framegraph_debugger_service = EditorFramegraphDebuggerService(
        rendering_manager=engine.rendering_manager,
        on_request_update=request_editor_render,
    )
    framegraph_debugger = project_stage.own(
        "framegraph debugger",
        build_native_framegraph_debugger(
            window_manager,
            framegraph_debugger_service.debugger,
            request_render=request_editor_render,
        ),
        cleanup=lambda: framegraph_debugger.close(),
    )
    connect_framegraph_debugger_command(
        debug_menu,
        shell.framegraph_debugger_command,
        framegraph_debugger,
    )
    if debug_resource is not None:
        framegraph_debugger.show_resource(debug_resource)

    from termin.editor_core.project_file_watcher import create_editor_project_file_watcher

    def on_resource_reloaded(name: str, kind: str) -> None:
        _logger.info("Native editor reloaded %s resource: %s", kind, name)
        request_editor_render()

    project_file_watcher, component_file_processor = create_editor_project_file_watcher(
        resource_manager,
        on_resource_reloaded=on_resource_reloaded,
    )
    project_stage.own(
        "project file watcher",
        project_file_watcher,
        cleanup=lambda: project_file_watcher.disable(),
    )
    project_stage.own("component file processor", component_file_processor)

    def rescan_file_resources() -> None:
        project_root = project_browser_controller.root_path
        if project_root is None:
            _logger.error("Native editor cannot scan resources without a project root")
            return
        project_file_watcher.watch_directory(str(project_root))

    project_editor_context = NativeProjectEditorContext(
        document=host.document,
        menu_bar=shell.menu_bar,
        dialog_service=dialog_service,
        viewport=editor_viewport,
        request_render=request_editor_render,
        extension_context=extension_context,
        get_scene=current_scene,
        get_selected_entity=lambda: selected_entity,
        select_scene_object=scene_tree.select_object,
        register_tool_inspector=inspector_host.register_tool_panel,
        unregister_tool_inspector=inspector_host.unregister_tool_panel,
        show_tool_inspector=inspector_host.show_tool_panel,
    )
    project_session_controller = NativeProjectSessionController(
        document=host.document,
        viewport=editor_viewport,
        refresh_ui=refresh_editor_ui,
        set_project_state=lambda _project_dir, project_name: session_presentation.update(project_name=project_name),
        log_to_console=log_build_message,
        rescan_file_resources=rescan_file_resources,
        set_project_browser_root=lambda project_dir: project_browser.set_root(Path(project_dir)),
        get_init_script_editor=lambda: project_editor_context,
        resolve_termin_shaderc=resolve_termin_shaderc,
        resolve_slangc=resolve_slangc,
        get_render_engine=lambda: engine.rendering_manager.render_engine,
        show_error=dialog_service.show_error,
    )

    from termin.editor_core.project_operations import sync_stdlib
    from termin.editor_core.resource_loader import ResourceLoader

    resource_loader = ResourceLoader(
        resource_manager,
        get_scene=current_scene,
        get_project_path=lambda: (
            None if project_browser_controller.root_path is None else str(project_browser_controller.root_path)
        ),
        on_resource_reloaded=on_resource_reloaded,
        log_message=log_build_message,
    )

    def project_dialog_directory() -> str:
        root_path = project_browser_controller.root_path
        return str(root_path) if root_path is not None else str(Path.home())

    def choose_material() -> None:
        dialog_service.show_open_file(
            "Load Material",
            project_dialog_directory(),
            "Shader Files (*.shader);;All Files (*)",
            lambda path: resource_loader.load_material_from_path(path) if path else None,
        )

    def deploy_stdlib() -> None:
        root_path = project_browser_controller.root_path
        if root_path is None:
            dialog_service.show_error("Deploy Standard Library", "Open a project first.")
            return
        try:
            sync_stdlib(root_path)
            log_build_message(f"Standard library deployed to {root_path}")
        except Exception as error:
            _logger.exception("Native standard library deployment failed")
            dialog_service.show_error("Deploy Standard Library", str(error))

    file_actions = {
        shell.close_scene_command: scene_file_controller.close_scene,
        shell.load_material_command: choose_material,
        shell.deploy_stdlib_command: deploy_stdlib,
        shell.exit_command: lambda: window.set_should_close(True),
    }

    def on_file_action(_menu_index: int, command_id: int, _command) -> None:
        action = file_actions.get(command_id)
        if action is not None:
            action()

    file_menu.connect_activated(on_file_action)

    def apply_undo_redo(action) -> None:
        action()
        undo_history_controller.refresh()
        update_undo_commands()
        scene_hierarchy_controller.rebuild()
        entity_inspector_controller.refresh()
        request_editor_render()

    def on_edit_action(_menu_index: int, command_id: int, _command) -> None:
        if command_id == shell.undo_command:
            apply_undo_redo(undo_stack.undo)
        elif command_id == shell.redo_command:
            apply_undo_redo(undo_stack.redo)

    edit_menu.connect_activated(on_edit_action)

    fullscreen = [False]

    def on_view_action(_menu_index: int, command_id: int, command) -> None:
        if command_id != shell.fullscreen_command:
            return
        fullscreen[0] = not fullscreen[0]
        window.set_fullscreen(fullscreen[0])
        command.checked = fullscreen[0]
        request_editor_render()

    view_menu.connect_activated(on_view_action)

    def on_camera_frustums(_menu_index: int, command_id: int, command) -> None:
        if command_id != shell.camera_frustums_command or native_viewport is None:
            return
        visible = not bool(native_viewport.interaction.camera_frustums_visible)
        native_viewport.interaction.set_camera_frustums_visible(visible)
        command.checked = visible
        request_editor_render()

    debug_menu.connect_activated(on_camera_frustums)
    if project_file is not None:
        project_session_controller.initialize_project(
            project_file,
            on_complete=lambda _success: scene_file_controller.load_last_scene(),
        )

    def prepare_code_for_play() -> bool:
        from termin.project_modules.runtime import get_project_modules_runtime

        modules_runtime = get_project_modules_runtime()
        if not modules_runtime.prepare_changed_modules_for_play():
            _logger.error(
                "Native module update before Play failed: %s",
                modules_runtime.last_error,
            )
            return False
        return True

    game_mode_controller = None
    if editor_scene_session is not None and render_scene_session is not None and display_workspace is not None:
        game_mode_model = GameModeModel(
            scene_manager=engine.scene_manager,
            editor_connector=EditorGameModeConnector(
                engine.scene_manager,
                editor_scene_session,
            ),
            rendering_controller=display_workspace,
            get_editor_scene_name=active_scene_name,
            render_binding_factory=lambda scene_name: PrimaryRenderSceneBinding(
                RenderGameModeConnector(render_scene_session),
                scene_name,
            ),
            scene_tree_controller=scene_hierarchy_controller,
            prepare_code_for_play=prepare_code_for_play,
        )
        game_mode_controller = NativeGameModeController(
            game_mode_model,
            menu_bar=game_menu,
            game_menu_model=shell.game_menu_model,
            game_play_command=shell.game_play_command,
            tool_bar=shell.tool_bar,
            toolbar_model=shell.toolbar_model,
            toolbar_play_command=shell.toolbar_play_command,
            toolbar_pause_command=shell.toolbar_pause_command,
            scene_hierarchy=scene_hierarchy_controller,
            status_bar=shell.status_bar,
            request_render=request_editor_render,
            on_playing_changed=lambda playing: session_presentation.update(playing=playing),
        )
        project_stage.own(
            "game mode controller",
            game_mode_controller,
            cleanup=lambda: _close_game_mode_controller(game_mode_controller),
        )

    def on_project_resource_settings_changed() -> None:
        try:
            project_file_watcher.rescan()
        except Exception:
            _logger.exception("Native project settings resource rescan failed")
        request_editor_render()

    project_settings_controller = ProjectSettingsController(
        on_resource_settings_changed=on_project_resource_settings_changed,
        on_render_settings_changed=request_editor_render,
    )
    project_settings_dialog = project_stage.own(
        "project settings dialog",
        build_native_project_settings_dialog(
            host.document,
            project_settings_controller,
            dialog_service=dialog_service,
            viewport=editor_viewport,
            request_render=request_editor_render,
        ),
        cleanup=lambda: project_settings_dialog.close(),
    )
    connect_project_settings_command(
        edit_menu,
        shell.project_settings_command,
        project_settings_dialog,
    )
    agent_types_dialog = project_stage.own(
        "agent types dialog",
        build_native_agent_types_dialog(
            host.document,
            NavigationSettingsController(on_changed=request_editor_render),
            dialog_service=dialog_service,
            viewport=editor_viewport,
            request_render=request_editor_render,
        ),
        cleanup=lambda: agent_types_dialog.close(),
    )
    navmesh_areas_dialog = project_stage.own(
        "NavMesh areas dialog",
        build_native_navmesh_areas_dialog(
            host.document,
            NavigationSettingsController(on_changed=request_editor_render),
            dialog_service=dialog_service,
            viewport=editor_viewport,
            request_render=request_editor_render,
        ),
        cleanup=lambda: navmesh_areas_dialog.close(),
    )
    connect_navigation_settings_command(navigation_menu, shell.agent_types_command, agent_types_dialog)
    connect_navigation_settings_command(navigation_menu, shell.navmesh_areas_command, navmesh_areas_dialog)

    resource_manager_controller = RegistryCatalogController(
        build_resource_manager_pages(resource_manager, project_file_watcher),
        copy_text=set_clipboard_text,
    )
    resource_manager_viewer = project_stage.own(
        "resource manager viewer",
        build_native_registry_catalog_viewer(
            host.document,
            resource_manager_controller,
            title="Resource Manager",
            viewport=editor_viewport,
            request_render=request_editor_render,
        ),
    )
    connect_registry_viewer_command(
        debug_menu,
        shell.resource_manager_command,
        resource_manager_viewer,
    )

    project_stage.own("core registry controller", core_registry_controller)
    project_stage.own("project file actions", project_file_actions)
    project_stage.own("project browser controller", project_browser_controller)
    project_stage.own("prefab edit controller", prefab_edit_controller)
    project_stage.own("scene file controller", scene_file_controller)
    project_stage.own("project build controller", project_build_controller)
    project_stage.own("framegraph debugger service", framegraph_debugger_service)
    project_stage.own("project editor context", project_editor_context)
    project_stage.own("project session controller", project_session_controller)
    project_stage.own("resource loader", resource_loader)
    project_stage.own("project settings controller", project_settings_controller)
    project_stage.own("resource manager controller", resource_manager_controller)

    automation_stage = session.begin_stage("automation services")
    scene_edit = automation_stage.own(
        "scene edit service",
        EditorSceneEditService(
            get_selected_entity=lambda: selected_entity,
            push_undo_command=push_undo_command,
            request_viewport_update=request_editor_render,
        ),
    )
    executor = automation_stage.own(
        "Python executor",
        EditorPythonExecutor(
            lambda: {
                "editor": host,
                "shell": shell,
                "scene": current_scene(),
                "current_scene": current_scene(),
                "selected_entity": selected_entity,
                "scene_edit": scene_edit,
                "scene_hierarchy_controller": scene_hierarchy_controller,
                "scene_tree": scene_tree,
                "viewport_list_controller": viewport_list_controller,
                "viewport_list": viewport_list,
                "display_workspace": display_workspace,
                "entity_inspector_controller": entity_inspector_controller,
                "entity_inspector": entity_inspector,
                "inspector_model": inspector_model,
                "inspector_host": inspector_host,
                "display_inspector_controller": display_inspector_controller,
                "viewport_inspector_controller": viewport_inspector_controller,
                "render_target_inspector_controller": render_target_inspector_controller,
                "component_extension_session": extension_session,
                "component_extension_projectors": extension_projectors,
                "undo_stack": undo_stack,
                "scene_manager": engine.scene_manager,
                "capture_editor_screenshot": host.capture_screenshot,
                "request_render_update": request_editor_render,
                "profiler_controller": profiler_controller,
                "profiler_panel": profiler_panel,
                "profiler_capture_coordinator": profiler_capture_coordinator,
                "frame_profiler_controller": frame_profiler_controller,
                "frame_profiler": frame_profiler,
                "modules_controller": modules_controller,
                "modules_panel": modules_panel,
                "registry_controller": registry_controller,
                "registry_viewer": registry_viewer,
                "core_registry_controller": core_registry_controller,
                "core_registry_viewer": core_registry_viewer,
                "resource_manager_controller": resource_manager_controller,
                "resource_manager_viewer": resource_manager_viewer,
                "project_file_watcher": project_file_watcher,
                "component_file_processor": component_file_processor,
                "project_browser_controller": project_browser_controller,
                "project_browser": project_browser,
                "project_build_controller": project_build_controller,
                "scene_file_controller": scene_file_controller,
                "game_mode_controller": game_mode_controller,
                "prefab_edit_controller": prefab_edit_controller,
                "open_prefab": open_prefab,
                "save_prefab": save_prefab,
                "exit_prefab": exit_prefab,
                "quest_openxr_build_dialog": quest_openxr_build_dialog,
                "pipeline_editor_controller": pipeline_editor_controller,
                "pipeline_editor": pipeline_editor,
                "framegraph_debugger": framegraph_debugger_service,
                "framegraph_debugger_native": framegraph_debugger_service.debugger,
                "framegraph_debugger_view": framegraph_debugger,
                "settings_controller": settings_controller,
                "settings_dialog": settings_dialog,
                "about_dialog": about_dialog,
                "undo_history_controller": undo_history_controller,
                "undo_history_dialog": undo_history_dialog,
                "audio_debugger_controller": audio_debugger_controller,
                "audio_debugger_dialog": audio_debugger_dialog,
                "scene_properties_dialog": scene_properties_dialog,
                "scene_names_dialog": scene_names_dialog,
                "shadow_settings_dialog": shadow_settings_dialog,
                "project_settings_controller": project_settings_controller,
                "project_settings_dialog": project_settings_dialog,
                "agent_types_dialog": agent_types_dialog,
                "navmesh_areas_dialog": navmesh_areas_dialog,
                "spacemouse": spacemouse,
                "spacemouse_settings_dialog": spacemouse_settings_dialog,
                "scene_manager_dialog": scene_manager_dialog,
                "editor_scene_session": editor_scene_session,
                "render_scene_session": render_scene_session,
                "native_viewport": native_viewport,
                "project_path": (
                    str(project_browser_controller.root_path)
                    if project_browser_controller.root_path is not None
                    else None
                ),
            },
        ),
    )
    python_console_controller = PythonConsoleController(executor)

    def activate_python_console_tab() -> None:
        shell.bottom_tabs.selected_index = 2

    python_console = automation_stage.own(
        "Python console",
        build_native_python_console(
            host.document,
            python_console_controller,
            viewport=editor_viewport,
            request_render=request_editor_render,
            embedded=True,
            activate_embedded=activate_python_console_tab,
        ),
        cleanup=lambda: python_console.close(),
    )
    shell.python_console_host.add_stretch_child(python_console.root)
    connect_python_console_command(
        debug_menu,
        shell.python_console_command,
        python_console,
    )
    mcp_server = start_editor_mcp_server(executor)
    if mcp_server is not None:
        automation_stage.own(
            "editor MCP server",
            mcp_server,
            cleanup=lambda: mcp_server.stop(),
        )
    if initial_scene is not None:
        engine.scene_manager.request_render()
        engine.tick_and_render(0.016)
    host.render()

    attach_native_editor_event_loop(
        session,
        engine,
        capture_profiler=capture_profiler,
        window_manager=window_manager,
        executor=executor,
        host=host,
        quest_openxr_build_dialog=quest_openxr_build_dialog,
        project_file_watcher=project_file_watcher,
        scene_structure_observer=scene_structure_observer,
        spacemouse=spacemouse,
        framegraph_debugger=framegraph_debugger,
        frame_profiler=frame_profiler,
        profiler_panel=profiler_panel,
        game_mode_controller=game_mode_controller,
        request_editor_render=request_editor_render,
        window=window,
    )


def init_editor_native(
    engine,
    debug_resource: str | None = None,
    no_scene: bool = False,
    *,
    _failure_injector: Callable[[str], None] | None = None,
) -> EditorSession:
    """Initialize one native document and register it with the C++ engine loop."""

    def compose(session: EditorSession) -> None:
        _compose_native_editor(
            session,
            engine,
            debug_resource=debug_resource,
            no_scene=no_scene,
        )

    return EditorSession.build(
        compose,
        failure_injector=_failure_injector,
        shutdown_engine=engine.shutdown,
    )


__all__ = ["EditorSession", "init_editor_native"]
