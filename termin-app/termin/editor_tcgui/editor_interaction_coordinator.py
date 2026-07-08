"""Undo, selection, gizmo, and viewport event coordination for EditorWindowTcgui."""

from __future__ import annotations

from typing import Callable

from tcbase import Action, Key, log

from termin.editor_core.editor_commands import (
    AddEntityCommand,
    DeleteEntityCommand,
    RenameEntityCommand,
    TransformEditCommand,
)


class EditorInteractionCoordinator:
    def __init__(
        self,
        *,
        undo_stack,
        undo_stack_changed,
        get_interaction_system: Callable[[], object | None],
        get_scene_tree_controller: Callable[[], object | None],
        get_inspector_controller: Callable[[], object | None],
        get_menu_bar_controller: Callable[[], object | None],
        get_editor_display: Callable[[], object | None],
        get_active_viewport_tool_count: Callable[[], int],
        dispatch_viewport_click: Callable[[object], bool],
        dispatch_viewport_pointer: Callable[[object], bool],
        dispatch_viewport_key: Callable[[object], bool],
        request_viewport_update: Callable[[], None],
    ) -> None:
        self._undo_stack = undo_stack
        self._undo_stack_changed = undo_stack_changed
        self._get_interaction_system = get_interaction_system
        self._get_scene_tree_controller = get_scene_tree_controller
        self._get_inspector_controller = get_inspector_controller
        self._get_menu_bar_controller = get_menu_bar_controller
        self._get_editor_display = get_editor_display
        self._get_active_viewport_tool_count = get_active_viewport_tool_count
        self._dispatch_viewport_click = dispatch_viewport_click
        self._dispatch_viewport_pointer = dispatch_viewport_pointer
        self._dispatch_viewport_key = dispatch_viewport_key
        self._request_viewport_update = request_viewport_update

    def push_undo_command(self, cmd, merge: bool = False) -> None:
        self._undo_stack.push(cmd, merge=merge)
        self._request_viewport_update()
        self.update_undo_redo_actions()
        self._undo_stack_changed.emit()

    def undo(self) -> None:
        cmd = self._undo_stack.undo()
        select_obj = self._select_object_after_undo(cmd)
        scene_tree_controller = self._get_scene_tree_controller()
        if scene_tree_controller is not None:
            scene_tree_controller.rebuild(select_obj=select_obj)

        self._request_viewport_update()
        self.resync_inspector_from_selection()
        self.update_undo_redo_actions()
        if cmd is not None:
            self._undo_stack_changed.emit()

    def redo(self) -> None:
        cmd = self._undo_stack.redo()
        select_obj = self._select_object_after_redo(cmd)
        scene_tree_controller = self._get_scene_tree_controller()
        if scene_tree_controller is not None:
            scene_tree_controller.rebuild(select_obj=select_obj)

        self._request_viewport_update()
        self.resync_inspector_from_selection()
        self.update_undo_redo_actions()
        if cmd is not None:
            self._undo_stack_changed.emit()

    def resync_inspector_from_selection(self) -> None:
        interaction_system = self._get_interaction_system()
        inspector_controller = self._get_inspector_controller()
        if interaction_system is None or inspector_controller is None:
            return
        selected = interaction_system.selection.selected
        if selected is None or not selected.valid():
            return
        inspector_controller.show_entity_inspector(selected)

    def update_undo_redo_actions(self) -> None:
        menu_bar_controller = self._get_menu_bar_controller()
        if menu_bar_controller is not None:
            menu_bar_controller.update_undo_redo_actions()

    def sync_gizmo_target(self) -> None:
        interaction_system = self._get_interaction_system()
        if interaction_system is None:
            return

        if self._get_active_viewport_tool_count() > 0:
            interaction_system.set_gizmo_target(None)
            self._request_viewport_update()
            return

        selected = interaction_system.selection.selected
        if selected is not None and selected.valid():
            interaction_system.set_gizmo_target(selected)
            self.update_gizmo_screen_scale()
        else:
            interaction_system.set_gizmo_target(None)
        self._request_viewport_update()

    def on_entity_selected_from_state(self, entity) -> None:
        scene_tree_controller = self._get_scene_tree_controller()
        if scene_tree_controller is not None:
            scene_tree_controller.select_object(entity)
        inspector_controller = self._get_inspector_controller()
        if inspector_controller is not None:
            inspector_controller.show_entity_inspector(entity)

    def on_tree_object_selected(self, obj) -> None:
        inspector_controller = self._get_inspector_controller()
        if inspector_controller is not None:
            inspector_controller.resync_from_tree_selection(obj)

        interaction_system = self._get_interaction_system()
        if interaction_system is None:
            return

        from termin.scene import Entity

        if isinstance(obj, Entity):
            interaction_system.selection.select(obj)
        else:
            interaction_system.selection.clear()

    def on_selection_changed(self, entity) -> None:
        # The C++ UnifiedGizmoPass pulls its draw target from
        # EditorInteractionSystem::transform_gizmo, which is empty until
        # set_gizmo_target is called.
        self.sync_gizmo_target()
        scene_tree_controller = self._get_scene_tree_controller()
        if scene_tree_controller is not None and entity and entity.valid():
            scene_tree_controller.select_object(entity)
        inspector_controller = self._get_inspector_controller()
        if inspector_controller is not None and entity and entity.valid():
            inspector_controller.show_entity_inspector(entity)

    def on_hover_changed(self, entity) -> None:
        self._request_viewport_update()

    def on_editor_viewport_click(self, event) -> bool:
        return self._dispatch_viewport_click(event)

    def dispatch_viewport_pointer(self, event) -> bool:
        return self._dispatch_viewport_pointer(event)

    def on_editor_key(self, event) -> bool:
        if self._dispatch_viewport_key(event):
            return True
        if event.key == Key.DELETE.value and event.action == Action.PRESS.value:
            return self.delete_selected_entity()
        return False

    def delete_selected_entity(self) -> bool:
        interaction_system = self._get_interaction_system()
        if interaction_system is None:
            log.error("[EditorInteractionCoordinator] cannot delete selection: interaction system is not available")
            return False

        from termin.scene import Entity

        entity = interaction_system.selection.selected
        if not isinstance(entity, Entity) or not entity.valid():
            return False

        scene_tree_controller = self._get_scene_tree_controller()
        if scene_tree_controller is None:
            log.error("[EditorInteractionCoordinator] cannot delete selected entity: scene tree controller is not available")
            return False

        scene_tree_controller.operations.delete_entity(entity)
        return True

    def on_transform_end(self, old_pose, new_pose) -> None:
        interaction_system = self._get_interaction_system()
        tg = interaction_system.transform_gizmo if interaction_system is not None else None
        if tg is None or not tg.target.valid():
            return
        cmd = TransformEditCommand(
            transform=tg.target.transform,
            old_pose=old_pose,
            new_pose=new_pose,
        )
        self.push_undo_command(cmd, False)

    def update_gizmo_screen_scale(self) -> None:
        interaction_system = self._get_interaction_system()
        if interaction_system is None:
            return
        tg = interaction_system.transform_gizmo
        if tg is None or not tg.target.valid():
            return
        display = self._get_editor_display()
        if display is None or not display.viewports:
            return
        viewport = display.viewports[0]
        render_target = viewport.render_target if viewport is not None else None
        camera = render_target.camera if render_target is not None else None
        if camera is None or camera.entity is None:
            return
        camera_pos = camera.entity.transform.global_pose().lin
        gizmo_pos = tg.target.transform.global_pose().lin
        distance = (camera_pos - gizmo_pos).norm()
        tg.set_screen_scale(max(0.1, distance * 0.1))

    def _select_object_after_undo(self, cmd):
        if isinstance(cmd, AddEntityCommand):
            return cmd.parent_entity
        if isinstance(cmd, DeleteEntityCommand):
            return cmd.entity
        if isinstance(cmd, RenameEntityCommand):
            return cmd.entity
        return None

    def _select_object_after_redo(self, cmd):
        if isinstance(cmd, AddEntityCommand):
            return cmd.entity
        if isinstance(cmd, DeleteEntityCommand):
            return cmd.parent_entity
        if isinstance(cmd, RenameEntityCommand):
            return cmd.entity
        return None
