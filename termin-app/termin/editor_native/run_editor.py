"""Native editor root entrypoint used during production migration."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from termin.display import SDLBackendWindow, quit_sdl
from termin.editor_core.component_editor_extension import (
    ComponentEditorExtensionSession,
    ComponentExtensionPresentation,
)
from termin.editor_core.entity_inspector_model import EntityInspectorController
from termin.editor_core.inspector_resources import InspectorResourceCatalog
from termin.editor_core.pipeline_editor_model import PipelineEditorController
from termin.editor_core.framegraph_debugger_service import EditorFramegraphDebuggerService
from termin.editor_core.python_console_model import PythonConsoleController
from termin.editor_core.settings_model import EditorSettingsController
from termin.editor_core.about_model import build_editor_about_info
from termin.editor_core.profiler_model import ProfilerController
from termin.editor_core.project_browser_model import ProjectBrowserController
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
from termin.editor_core.project_session_controller import ProjectSessionController
from termin.editor_core.scene_file_controller import SceneFileController
from termin.editor_core.editor_state_io import EditorStateIO
from termin.editor_core.shader_runtime import resolve_slangc, resolve_termin_shaderc
from termin.editor_core.game_mode_model import GameModeModel
from termin.editor_core.game_mode_session_connectors import (
    EditorGameModeConnector,
    RenderGameModeConnector,
)
from termin.editor_core.navigation_settings_model import NavigationSettingsController
from termin.editor_core.spacemouse_controller import SpaceMouseController
from termin.editor_core.spacemouse_settings_model import SpaceMouseSettingsController
from termin.editor_core.scene_manager_model import SceneManagerController
from termin.editor_core.editor_scene_session import EditorSceneSession
from termin.editor_core.render_scene_session import RenderSceneSession
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
from termin.editor_native.quest_openxr_build_dialog import (
    build_native_quest_openxr_build_dialog,
)
from termin.editor_native.entity_inspector import build_native_entity_inspector
from termin.editor_native.profiler_panel import (
    build_native_profiler_panel,
    connect_profiler_menu_toggle,
)
from termin.editor_native.pipeline_editor import (
    build_native_pipeline_editor,
    connect_pipeline_editor_command,
)
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
from termin.editor_native.registry_viewer import (
    build_native_registry_catalog_viewer,
    build_native_registry_viewer,
    connect_registry_viewer_command,
)
from termin.editor_native.scene_tree import build_native_scene_tree
from termin.editor_native.shell import build_native_editor_shell
from termin.editor_native.ui_host import NativeUiHost
from termin.editor_native.viewport_list import build_native_viewport_list
from termin.gui_native import Rect, WidgetRef


_logger = logging.getLogger(__name__)


def _smoke_frame_limit() -> int:
    value = os.environ.get("TERMIN_EDITOR_NATIVE_SMOKE_FRAMES", "0")
    try:
        return max(int(value), 0)
    except ValueError:
        return 0


def init_editor_native(debug_resource: str | None = None, no_scene: bool = False) -> None:
    """Initialize one native document and register it with the C++ engine loop."""

    from termin.bootstrap import bootstrap_editor
    from termin.editor_core.resource_manager import configure_editor_resource_manager_factory
    from termin.editor_core.mcp_server import start_editor_mcp_server
    from termin.editor_core.python_executor import EditorPythonExecutor
    from termin.engine import EngineCore, create_scene, scene as engine_scene

    bootstrap_editor()
    configure_editor_resource_manager_factory()
    from termin.editor_core.resource_manager import ResourceManager

    resource_manager = ResourceManager.instance()
    from termin.editor_core.resource_loader import register_editor_builtin_resources

    register_editor_builtin_resources(resource_manager)
    engine = EngineCore.instance()
    if engine is None:
        raise RuntimeError("EngineCore not created. Must be called from C++ entry point.")

    from termin.editor_core.shader_runtime import configure_sdk_shader_runtime

    configure_sdk_shader_runtime("native-editor")
    window = SDLBackendWindow("Termin Editor — Native UI", 1280, 720)
    window.maximize()
    host = NativeUiHost(window)
    shell = build_native_editor_shell(host.document)

    def request_editor_render() -> None:
        engine.scene_manager.request_render()
        host.request_render_update()

    def set_profile_ui(enabled: bool) -> None:
        engine.profile_ui = enabled

    profiler_controller = ProfilerController(
        get_include_ui=lambda: bool(engine.profile_ui),
        set_include_ui=set_profile_ui,
    )
    profiler_panel = build_native_profiler_panel(host.document, profiler_controller)
    shell.workspace_host.add_fixed_child(profiler_panel.root, 480.0)
    profiler_panel.root.visible = False

    connect_profiler_menu_toggle(
        shell.menu_bar,
        shell.profiler_command,
        profiler_panel,
        request_editor_render,
    )

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
        engine.scene_manager.set_mode(editor_scene_name, engine_scene.SceneMode.STOP)
    undo_stack = UndoStack()
    dialog_service = NativeDialogService(
        host.document,
        viewport=editor_viewport,
        request_render=request_editor_render,
    )
    undo_history_controller = UndoHistoryController(undo_stack)

    def push_undo_command(command, merge: bool = False) -> None:
        undo_stack.push(command, merge=merge)
        undo_history_controller.refresh()

    scene_properties_dialog = None
    scene_names_dialog = None
    shadow_settings_dialog = None
    scene_properties_controller = None
    scene_names_controller = None
    shadow_settings_controller = None
    if initial_scene is not None:
        scene_properties_controller = ScenePropertiesController(
            initial_scene,
            resource_manager=resource_manager,
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
        scene_names_controller = SceneNamesController(initial_scene)
        scene_names_dialog = build_native_scene_names_dialog(
            host.document,
            scene_names_controller,
            viewport=editor_viewport,
            request_render=request_editor_render,
        )
        shadow_settings_controller = ShadowSettingsController(
            initial_scene, on_changed=request_editor_render
        )
        shadow_settings_dialog = build_native_shadow_settings_dialog(
            host.document,
            shadow_settings_controller,
            viewport=editor_viewport,
            request_render=request_editor_render,
        )
        for command_id, scene_dialog in (
            (shell.scene_properties_command, scene_properties_dialog),
            (shell.scene_names_command, scene_names_dialog),
            (shell.shadow_settings_command, shadow_settings_dialog),
        ):
            connect_scene_settings_command(shell.menu_bar, command_id, scene_dialog)

    undo_history_dialog = build_native_undo_history_dialog(
        host.document,
        undo_history_controller,
        viewport=editor_viewport,
        request_render=request_editor_render,
    )
    connect_diagnostic_command(
        shell.menu_bar,
        shell.undo_history_command,
        undo_history_dialog,
    )
    audio_debugger_controller = create_audio_debugger_controller()
    audio_debugger_dialog = build_native_audio_debugger_dialog(
        host.document,
        audio_debugger_controller,
        viewport=editor_viewport,
        request_render=request_editor_render,
    )
    connect_diagnostic_command(
        shell.menu_bar,
        shell.audio_debugger_command,
        audio_debugger_dialog,
    )
    settings_controller = EditorSettingsController()
    host.apply_font_size(settings_controller.load().font_size)
    settings_dialog = build_native_settings_dialog(
        host.document,
        settings_controller,
        dialog_service=dialog_service,
        viewport=editor_viewport,
        request_render=request_editor_render,
        apply_font_size=host.apply_font_size,
    )
    connect_settings_command(
        shell.menu_bar,
        shell.settings_command,
        settings_dialog,
    )
    from tgfx import compiled_backend_name

    about_dialog = build_native_about_dialog(
        host.document,
        build_editor_about_info(backend_name=compiled_backend_name()),
        viewport=editor_viewport,
        request_render=request_editor_render,
    )
    connect_about_command(shell.menu_bar, shell.about_command, about_dialog)
    selected_entity = None
    display_workspace: NativeDisplayWorkspace | None = None
    native_viewport: NativeEditorViewport | None = None
    entity_inspector_controller = EntityInspectorController(undo_handler=push_undo_command)
    entity_inspector_controller.set_scene(initial_scene)
    entity_inspector = build_native_entity_inspector(
        host.document,
        entity_inspector_controller,
        request_render=request_editor_render,
        viewport=editor_viewport,
        show_color_dialog=dialog_service.show_color,
        show_layer_mask_dialog=dialog_service.show_layer_mask,
        resource_catalog=InspectorResourceCatalog(resource_manager),
    )
    shell.inspector_host.add_stretch_child(entity_inspector.root)
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

    def on_component_selected(entity: object | None, component_ref: object | None) -> None:
        if entity is None or component_ref is None:
            extension_session.clear()
            return
        extension_session.select_component(entity, component_ref, component_ref.type_name)

    entity_inspector_controller.set_component_selection_changed_handler(on_component_selected)

    def on_scene_object_selected(obj: object | None) -> None:
        nonlocal selected_entity
        selected_entity = obj
        entity_inspector.set_target(obj)
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
    scene_tree = build_native_scene_tree(
        host.document,
        scene_hierarchy_controller,
        viewport=editor_viewport,
        request_render=request_editor_render,
    )
    shell.hierarchy_host.add_fixed_child(scene_tree.root, 220.0)
    host.router.file_drop_handler = scene_tree.drop_file

    viewport_list_controller = ViewportListController()
    viewport_list = build_native_viewport_list(
        host.document,
        viewport_list_controller,
        viewport=editor_viewport,
        request_render=request_editor_render,
        show_input=dialog_service.show_input,
    )
    shell.hierarchy_host.add_stretch_child(viewport_list.root)

    def sync_viewport_list() -> None:
        displays = [] if display_workspace is None else list(display_workspace.displays)
        display_pointers = {display.tc_display_ptr for display in displays}
        for display in engine.rendering_manager.displays:
            if display.tc_display_ptr not in display_pointers:
                displays.append(display)
                display_pointers.add(display.tc_display_ptr)
        viewport_list_controller.set_displays(displays)
        viewport_list_controller.set_render_targets(engine.rendering_manager.managed_render_targets)

    def on_viewport_list_entity_selected(entity) -> None:
        scene_tree.select_object(entity)

    def on_viewport_list_display_selected(display) -> None:
        if display is not None and display_workspace is not None:
            display_workspace.select_display(display)
        shell.status_bar.text = (
            "Ready | Display: none" if display is None else f"Ready | Display: {display.name or 'unnamed'}"
        )
        request_editor_render()

    def on_viewport_list_viewport_selected(viewport) -> None:
        shell.status_bar.text = (
            "Ready | Viewport: none" if viewport is None else f"Ready | Viewport: {viewport.name or 'unnamed'}"
        )
        request_editor_render()

    def on_viewport_list_target_selected(target) -> None:
        shell.status_bar.text = (
            "Ready | Render target: none" if target is None else f"Ready | Render target: {target.name or 'unnamed'}"
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
        try:
            display_workspace.configure_viewport_input(display, viewport)
        except Exception:
            _logger.exception("Native workspace failed to configure viewport input")
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
        display.remove_viewport(viewport)
        sync_viewport_list()
        request_editor_render()

    def add_display() -> None:
        if display_workspace is None:
            _logger.error("Native viewport list requested a display before workspace creation")
            return
        display_workspace.create_display()
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
        display_workspace = NativeDisplayWorkspace.create(
            host.document,
            shell.workspace_host,
            device=host.device,
            rendering_manager=engine.rendering_manager,
            scene=initial_scene,
            request_render=request_editor_render,
        )
        native_viewport = display_workspace.editor_viewport
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
            entity_inspector.set_target(transform_gizmo.target)
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
        engine.scene_manager.set_on_after_render(native_viewport.after_render)
        sync_viewport_list()

    from termin.editor_core.rendering_model import RenderingModel

    rendering_model = RenderingModel(engine.rendering_manager)
    if display_workspace is not None:
        engine.rendering_manager.set_display_factory(display_workspace.create_display)

    render_scene_session = None
    if display_workspace is not None:
        render_scene_session = RenderSceneSession(
            engine.scene_manager,
            rendering_model,
            display_workspace,
            sync_viewports=sync_viewport_list,
            request_render=request_editor_render,
        )

    spacemouse = SpaceMouseController()
    if native_viewport is not None:
        spacemouse.open(native_viewport.attachment, request_editor_render)
    spacemouse_settings_dialog = build_native_spacemouse_settings_dialog(
        host.document,
        SpaceMouseSettingsController(spacemouse, on_changed=request_editor_render),
        viewport=editor_viewport,
        request_render=request_editor_render,
    )
    connect_spacemouse_settings_command(
        shell.menu_bar,
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
            entity_inspector.set_target(None)
            native_viewport.select_scene_object(None)

        def scene_switched(scene) -> None:
            active_scene[0] = scene
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

    scene_manager_dialog = build_native_scene_manager_dialog(
        host.document,
        SceneManagerController(
            engine.scene_manager,
            get_editor_attachment=lambda: (
                None if native_viewport is None else native_viewport.attachment
            ),
            on_editor_attach=attach_editor_scene if editor_scene_session is not None else None,
            on_editor_detach=detach_editor_scene if editor_scene_session is not None else None,
            on_render_attach=None if render_scene_session is None else render_scene_session.attach,
            on_render_detach=None if render_scene_session is None else render_scene_session.detach,
            on_changed=request_editor_render,
        ),
        dialog_service=dialog_service,
        viewport=editor_viewport,
        request_render=request_editor_render,
    )
    connect_scene_manager_command(
        shell.menu_bar,
        shell.scene_manager_command,
        scene_manager_dialog,
    )

    registry_viewer = build_native_registry_viewer(
        host.document,
        registry_controller,
        viewport=editor_viewport,
        request_render=request_editor_render,
    )
    connect_registry_viewer_command(
        shell.menu_bar,
        shell.inspect_registry_command,
        registry_viewer,
    )

    core_registry_controller = RegistryCatalogController(
        build_core_registry_pages(),
        copy_text=set_clipboard_text,
    )
    core_registry_viewer = build_native_registry_catalog_viewer(
        host.document,
        core_registry_controller,
        title="Core Registry",
        viewport=editor_viewport,
        request_render=request_editor_render,
    )
    connect_registry_viewer_command(
        shell.menu_bar,
        shell.core_registry_command,
        core_registry_viewer,
    )

    def on_project_file_selected(path: Path) -> None:
        _logger.debug("Native project browser selected: %s", path)

    def on_project_file_activated(path: Path) -> None:
        _logger.info("Native project browser activated: %s", path)

    project_browser_controller = ProjectBrowserController(
        on_file_selected=on_project_file_selected,
        on_file_activated=on_project_file_activated,
        copy_text=set_clipboard_text,
    )
    project_browser = build_native_project_browser(
        host.document,
        project_browser_controller,
        viewport=editor_viewport,
        request_render=request_editor_render,
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
            if (
                candidate_handle.index == handle.index
                and candidate_handle.generation == handle.generation
            ):
                return name
        _logger.error("Native editor active scene is not registered in SceneManager")
        return None

    def log_build_message(message: str) -> None:
        _logger.info("Project build: %s", message)
        shell.status_bar.text = message
        request_editor_render()

    editor_state_io = None
    if native_viewport is not None:
        editor_state_io = EditorStateIO(
            native_viewport.attachment,
            native_viewport.interaction,
        )
        editor_state_io.get_scene = current_scene
        editor_state_io.on_entity_selected = scene_tree.select_object
        editor_state_io.get_expanded_entity_uuids = (
            scene_hierarchy_controller.get_expanded_entity_uuids
        )
        editor_state_io.set_expanded_entity_uuids = (
            scene_hierarchy_controller.set_expanded_entity_uuids
        )

    scene_file_controller = SceneFileController(
        scene_manager=engine.scene_manager,
        get_dialog_service=lambda: dialog_service,
        get_editor_scene_name=active_scene_name,
        set_editor_scene_name=lambda _name: None,
        get_scene=current_scene,
        get_project_path=lambda: (
            None
            if project_browser_controller.root_path is None
            else str(project_browser_controller.root_path)
        ),
        get_editor_state_io=lambda: editor_state_io,
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
        observe_scene_events=lambda _scene: None,
        on_rendering_changed=sync_viewport_list,
        request_viewport_update=request_editor_render,
        update_window_title=lambda: None,
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

    shell.menu_bar.connect_activated(on_scene_file_command)

    def on_toolbar_scene_file_command(_index: int, command_id: int, _command) -> None:
        if command_id == shell.toolbar_save_command:
            scene_file_controller.save_scene()

    shell.tool_bar.connect_activated(on_toolbar_scene_file_command)

    quest_openxr_build_dialog = build_native_quest_openxr_build_dialog(
        host.document,
        viewport=editor_viewport,
        request_render=request_editor_render,
    )

    def show_quest_openxr_build(entry) -> None:
        quest_openxr_build_dialog.show_entry(entry, on_log=log_build_message)

    project_build_controller = ProjectBuildController(
        scene_manager=engine.scene_manager,
        get_current_project_path=lambda: (
            None
            if project_browser_controller.root_path is None
            else str(project_browser_controller.root_path)
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

    shell.menu_bar.connect_activated(on_project_build_command)

    pipeline_editor_controller = PipelineEditorController()
    pipeline_directory = project_browser_controller.root_path or Path.cwd()
    pipeline_editor = build_native_pipeline_editor(
        host.document,
        pipeline_editor_controller,
        dialog_service=dialog_service,
        viewport=editor_viewport,
        request_render=request_editor_render,
        default_directory=pipeline_directory,
    )
    connect_pipeline_editor_command(
        shell.menu_bar,
        shell.pipeline_editor_command,
        pipeline_editor,
    )

    framegraph_debugger_service = EditorFramegraphDebuggerService(
        get_rendering_controller=lambda: rendering_model,
        on_request_update=request_editor_render,
    )
    framegraph_debugger = build_native_framegraph_debugger(
        host.document,
        framegraph_debugger_service.model,
        context=host.context,
        device=host.device,
        viewport=editor_viewport,
        request_render=request_editor_render,
        add_pre_render_callback=host.add_pre_render_callback,
        remove_pre_render_callback=host.remove_pre_render_callback,
    )
    connect_framegraph_debugger_command(
        shell.menu_bar,
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

    def rescan_file_resources() -> None:
        project_root = project_browser_controller.root_path
        if project_root is None:
            _logger.error("Native editor cannot scan resources without a project root")
            return
        project_file_watcher.watch_directory(str(project_root))

    project_session_controller = ProjectSessionController(
        set_project_state=lambda _project_dir, _project_name: None,
        log_to_console=log_build_message,
        rescan_file_resources=rescan_file_resources,
        set_project_browser_root=lambda project_dir: project_browser.set_root(
            Path(project_dir)
        ),
        get_init_script_editor=lambda: None,
        resolve_termin_shaderc=resolve_termin_shaderc,
        resolve_slangc=resolve_slangc,
        show_error=dialog_service.show_error,
    )
    if project_file is not None:
        project_session_controller.load_project(
            project_file,
            on_complete=scene_file_controller.load_last_scene,
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
        if not component_file_processor.reload_dirty_components():
            _logger.error("Native loose Python component update before Play failed")
            return False
        return True

    game_mode_controller = None
    if (
        editor_scene_session is not None
        and render_scene_session is not None
        and display_workspace is not None
    ):
        game_mode_model = GameModeModel(
            scene_manager=engine.scene_manager,
            editor_connector=EditorGameModeConnector(
                engine.scene_manager,
                editor_scene_session,
            ),
            rendering_controller=display_workspace,
            get_editor_scene_name=active_scene_name,
            scene_tree_controller=scene_hierarchy_controller,
            render_connector=RenderGameModeConnector(render_scene_session),
            prepare_code_for_play=prepare_code_for_play,
        )
        game_mode_controller = NativeGameModeController(
            game_mode_model,
            menu_bar=shell.menu_bar,
            game_menu_model=shell.game_menu_model,
            game_play_command=shell.game_play_command,
            tool_bar=shell.tool_bar,
            toolbar_model=shell.toolbar_model,
            toolbar_play_command=shell.toolbar_play_command,
            scene_hierarchy=scene_hierarchy_controller,
            status_bar=shell.status_bar,
            request_render=request_editor_render,
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
    project_settings_dialog = build_native_project_settings_dialog(
        host.document,
        project_settings_controller,
        dialog_service=dialog_service,
        viewport=editor_viewport,
        request_render=request_editor_render,
    )
    connect_project_settings_command(
        shell.menu_bar,
        shell.project_settings_command,
        project_settings_dialog,
    )
    agent_types_dialog = build_native_agent_types_dialog(
        host.document,
        NavigationSettingsController(on_changed=request_editor_render),
        dialog_service=dialog_service,
        viewport=editor_viewport,
        request_render=request_editor_render,
    )
    navmesh_areas_dialog = build_native_navmesh_areas_dialog(
        host.document,
        NavigationSettingsController(on_changed=request_editor_render),
        dialog_service=dialog_service,
        viewport=editor_viewport,
        request_render=request_editor_render,
    )
    connect_navigation_settings_command(
        shell.menu_bar, shell.agent_types_command, agent_types_dialog
    )
    connect_navigation_settings_command(
        shell.menu_bar, shell.navmesh_areas_command, navmesh_areas_dialog
    )

    resource_manager_controller = RegistryCatalogController(
        build_resource_manager_pages(resource_manager, project_file_watcher),
        copy_text=set_clipboard_text,
    )
    resource_manager_viewer = build_native_registry_catalog_viewer(
        host.document,
        resource_manager_controller,
        title="Resource Manager",
        viewport=editor_viewport,
        request_render=request_editor_render,
    )
    connect_registry_viewer_command(
        shell.menu_bar,
        shell.resource_manager_command,
        resource_manager_viewer,
    )

    executor = EditorPythonExecutor(
        lambda: {
            "editor": host,
            "scene": current_scene(),
            "current_scene": current_scene(),
            "selected_entity": selected_entity,
            "scene_hierarchy_controller": scene_hierarchy_controller,
            "scene_tree": scene_tree,
            "viewport_list_controller": viewport_list_controller,
            "viewport_list": viewport_list,
            "display_workspace": display_workspace,
            "entity_inspector_controller": entity_inspector_controller,
            "entity_inspector": entity_inspector,
            "component_extension_session": extension_session,
            "component_extension_projectors": extension_projectors,
            "undo_stack": undo_stack,
            "scene_manager": engine.scene_manager,
            "capture_editor_screenshot": host.capture_screenshot,
            "request_render_update": request_editor_render,
            "profiler_controller": profiler_controller,
            "profiler_panel": profiler_panel,
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
            "quest_openxr_build_dialog": quest_openxr_build_dialog,
            "pipeline_editor_controller": pipeline_editor_controller,
            "pipeline_editor": pipeline_editor,
            "framegraph_debugger": framegraph_debugger_service,
            "framegraph_debugger_model": framegraph_debugger_service.model,
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
                str(project_browser_controller.root_path) if project_browser_controller.root_path is not None else None
            ),
        }
    )
    python_console_controller = PythonConsoleController(executor)
    python_console = build_native_python_console(
        host.document,
        python_console_controller,
        viewport=editor_viewport,
        request_render=request_editor_render,
    )
    connect_python_console_command(
        shell.menu_bar,
        shell.python_console_command,
        python_console,
    )
    mcp_server = start_editor_mcp_server(executor)
    if initial_scene is not None:
        engine.scene_manager.request_render()
        engine.tick_and_render(0.016)
    host.render()

    frame_limit = _smoke_frame_limit()
    frame_count = 0

    def poll_events() -> None:
        nonlocal frame_count
        # The root shell and initial scene are owned by this engine-loop closure.
        _ = (
            shell,
            initial_scene,
            profiler_panel,
            registry_viewer,
            core_registry_viewer,
            resource_manager_viewer,
            project_browser,
            pipeline_editor,
            framegraph_debugger,
            python_console,
            settings_dialog,
            about_dialog,
            undo_history_dialog,
            audio_debugger_dialog,
            scene_properties_dialog,
            scene_names_dialog,
            shadow_settings_dialog,
            project_settings_dialog,
            agent_types_dialog,
            navmesh_areas_dialog,
            spacemouse_settings_dialog,
            scene_manager_dialog,
            scene_tree,
            viewport_list,
            display_workspace,
            entity_inspector,
        )
        keep_running, routed = host.poll_events()
        if not keep_running:
            return
        if routed > 0:
            host.request_render_update()
        if executor.process_pending() > 0:
            host.request_render_update()
        if quest_openxr_build_dialog.poll() > 0:
            host.request_render_update()
        project_file_watcher.poll()
        spacemouse.poll()
        framegraph_debugger.update()
        if profiler_panel.root.visible and profiler_panel.update():
            host.request_render_update()
        if host.render_requested:
            host.render()
        frame_count += 1
        if frame_limit > 0 and frame_count >= frame_limit:
            window.set_should_close(True)

    def should_continue() -> bool:
        return not window.should_close()

    def on_shutdown() -> None:
        if mcp_server is not None:
            mcp_server.stop()
        project_file_watcher.disable()
        scene_hierarchy_controller.set_snapshot_changed_handler(None)
        entity_inspector_controller.set_snapshot_changed_handler(None)
        entity_inspector_controller.set_component_selection_changed_handler(None)
        try:
            extension_session.clear()
        except Exception:
            _logger.exception("Native component extension shutdown cleanup failed")
        if game_mode_controller is not None:
            try:
                if game_mode_controller.model.is_game_mode:
                    game_mode_controller.model.toggle_game_mode()
                game_mode_controller.close()
            except Exception:
                _logger.exception("Native game mode shutdown cleanup failed")
        extension_context.on_viewport_tool_state_changed = None
        extension_context.viewport_geometry = None
        engine.scene_manager.set_on_after_render(None)
        engine.rendering_manager.set_display_factory(None)
        try:
            about_dialog.close()
        except Exception:
            _logger.exception("Native About dialog shutdown cleanup failed")
        try:
            quest_openxr_build_dialog.close()
        except Exception:
            _logger.exception("Native Quest/OpenXR build dialog shutdown cleanup failed")
        try:
            undo_history_dialog.close()
        except Exception:
            _logger.exception("Native undo history dialog shutdown cleanup failed")
        try:
            audio_debugger_dialog.close()
        except Exception:
            _logger.exception("Native audio debugger shutdown cleanup failed")
        for name, scene_dialog in (
            ("scene properties", scene_properties_dialog),
            ("scene names", scene_names_dialog),
            ("shadow settings", shadow_settings_dialog),
        ):
            if scene_dialog is None:
                continue
            try:
                scene_dialog.close()
            except Exception:
                _logger.exception("Native %s dialog shutdown cleanup failed", name)
        try:
            project_settings_dialog.close()
        except Exception:
            _logger.exception("Native project settings dialog shutdown cleanup failed")
        for name, navigation_dialog in (
            ("agent types", agent_types_dialog),
            ("NavMesh areas", navmesh_areas_dialog),
        ):
            try:
                navigation_dialog.close()
            except Exception:
                _logger.exception("Native %s dialog shutdown cleanup failed", name)
        try:
            spacemouse_settings_dialog.close()
            spacemouse.close()
        except Exception:
            _logger.exception("Native SpaceMouse shutdown cleanup failed")
        try:
            scene_manager_dialog.close()
        except Exception:
            _logger.exception("Native Scene Manager shutdown cleanup failed")
        try:
            settings_dialog.close()
        except Exception:
            _logger.exception("Native settings dialog shutdown cleanup failed")
        try:
            python_console.close()
        except Exception:
            _logger.exception("Native Python console shutdown cleanup failed")
        try:
            framegraph_debugger.close()
        except Exception:
            _logger.exception("Native framegraph debugger shutdown cleanup failed")
        try:
            pipeline_editor.close()
        except Exception:
            _logger.exception("Native pipeline editor shutdown cleanup failed")
        if display_workspace is not None:
            try:
                display_workspace.close()
            except Exception:
                _logger.exception("Native display workspace shutdown cleanup failed")
        if initial_scene is not None:
            engine.scene_manager.unregister_scene(editor_scene_name)
        try:
            engine.rendering_manager.shutdown()
        except Exception:
            _logger.exception("Native rendering manager shutdown failed")
        host.close()
        quit_sdl()

    engine.set_poll_events_callback(poll_events)
    engine.set_should_continue_callback(should_continue)
    engine.set_on_shutdown_callback(on_shutdown)


__all__ = ["init_editor_native"]
