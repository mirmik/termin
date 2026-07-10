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
from termin.editor_native.component_extensions import (
    NativeComponentExtensionContext,
    NativeComponentExtensionProjectorRegistry,
    register_native_component_extensions,
)
from termin.editor_native.dialog_service import NativeDialogService
from termin.editor_native.editor_viewport import NativeEditorViewport
from termin.editor_native.entity_inspector import build_native_entity_inspector
from termin.editor_native.profiler_panel import (
    build_native_profiler_panel,
    connect_profiler_menu_toggle,
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
    selected_entity = None
    native_viewport: NativeEditorViewport | None = None
    entity_inspector_controller = EntityInspectorController(undo_handler=undo_stack.push)
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
        undo_handler=undo_stack.push,
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
    shell.project_host.add_fixed_child(scene_tree.root, 300.0)
    host.router.file_drop_handler = scene_tree.drop_file

    if initial_scene is not None:
        native_viewport = NativeEditorViewport.create(
            host.document,
            shell.workspace_host,
            device=host.device,
            rendering_manager=engine.rendering_manager,
            scene=initial_scene,
            request_render=request_editor_render,
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
            undo_stack.push(
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
        if project_path.is_file() and project_path.suffix == ".terminproj":
            from termin.editor_core.project_context import set_current_project_path

            set_current_project_path(project_path.parent)
            project_browser.set_root(project_path.parent)
        else:
            _logger.error("Native editor ignored invalid startup project: %s", project_file)

    from termin.editor_core.project_file_watcher import create_editor_project_file_watcher

    def on_resource_reloaded(name: str, kind: str) -> None:
        _logger.info("Native editor reloaded %s resource: %s", kind, name)
        request_editor_render()

    project_file_watcher, component_file_processor = create_editor_project_file_watcher(
        resource_manager,
        on_resource_reloaded=on_resource_reloaded,
    )
    if project_browser_controller.root_path is not None:
        project_file_watcher.watch_directory(str(project_browser_controller.root_path))

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
            "scene": initial_scene,
            "current_scene": initial_scene,
            "selected_entity": selected_entity,
            "scene_hierarchy_controller": scene_hierarchy_controller,
            "scene_tree": scene_tree,
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
            "native_viewport": native_viewport,
            "project_path": (
                str(project_browser_controller.root_path) if project_browser_controller.root_path is not None else None
            ),
        }
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
            scene_tree,
            entity_inspector,
        )
        keep_running, routed = host.poll_events()
        if not keep_running:
            return
        if routed > 0:
            host.request_render_update()
        if executor.process_pending() > 0:
            host.request_render_update()
        project_file_watcher.poll()
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
        extension_context.on_viewport_tool_state_changed = None
        extension_context.viewport_geometry = None
        engine.scene_manager.set_on_after_render(None)
        if native_viewport is not None:
            try:
                native_viewport.close()
            except Exception:
                _logger.exception("Native editor viewport shutdown cleanup failed")
        if initial_scene is not None:
            engine.scene_manager.unregister_scene(editor_scene_name)
        host.close()
        quit_sdl()

    engine.set_poll_events_callback(poll_events)
    engine.set_should_continue_callback(should_continue)
    engine.set_on_shutdown_callback(on_shutdown)


__all__ = ["init_editor_native"]
